from __future__ import annotations
import copy
import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
Json = Dict[str, Any]

def blind_reasoning_summaries(messages):
    blinded = copy.deepcopy(messages)
    for message in blinded:
        for block in message.get('content', []) if isinstance(message, dict) else []:
            reasoning = block.get('reasoningContent') if isinstance(block, dict) else None
            reasoning_text = reasoning.get('reasoningText') if isinstance(reasoning, dict) else None
            if isinstance(reasoning_text, dict) and 'text' in reasoning_text:
                reasoning_text['text'] = ''
    return blinded

def strip_reasoning_blocks(content):
    """Return the visible assistant content without provider reasoning blocks."""
    return [
        copy.deepcopy(block)
        for block in content
        if not (isinstance(block, dict) and 'reasoningContent' in block)
    ]

def text_only_priming_messages(step, instruction):
    """Keep prior turn text, remove prior signed blocks, and retain a blinded signed target."""
    messages = copy.deepcopy(step.prefix_messages)
    for message in messages:
        if isinstance(message, dict) and message.get('role') == 'assistant':
            message['content'] = strip_reasoning_blocks(message.get('content', []))
    target = blind_reasoning_summaries([
        {'role': 'assistant', 'content': copy.deepcopy(step.assistant_content)}
    ])[0]
    messages.append(target)
    messages.append({'role': 'user', 'content': [{'text': instruction}]})
    return messages

@dataclass(frozen=True)
class BoundaryMarkers:
    start: str
    end: str

@dataclass(frozen=True)
class ToolCall:
    tool_use_id: str
    name: str
    arguments: Json

@dataclass
class BedrockResponse:
    content: List[Json]
    stop_reason: str
    usage: Json
    raw: Json = field(repr=False)

    @property
    def text(self) -> str:
        return ''.join((str(block.get('text', '')) for block in self.content if isinstance(block, dict) and 'text' in block)).strip()

    @property
    def signatures(self) -> List[str]:
        found: List[str] = []
        for block in self.content:
            reasoning = block.get('reasoningContent') if isinstance(block, dict) else None
            text = reasoning.get('reasoningText') if isinstance(reasoning, dict) else None
            signature = text.get('signature') if isinstance(text, dict) else None
            if signature:
                found.append(str(signature))
        return found

    @property
    def reasoning_summary(self) -> str:
        parts: List[str] = []
        for block in self.content:
            reasoning = block.get('reasoningContent') if isinstance(block, dict) else None
            text = reasoning.get('reasoningText') if isinstance(reasoning, dict) else None
            summary = text.get('text') if isinstance(text, dict) else None
            if summary:
                parts.append(str(summary))
        return '\n'.join(parts).strip()

    @property
    def tool_calls(self) -> List[ToolCall]:
        calls: List[ToolCall] = []
        for block in self.content:
            value = block.get('toolUse') if isinstance(block, dict) else None
            if not isinstance(value, dict):
                continue
            calls.append(ToolCall(tool_use_id=str(value.get('toolUseId', '')), name=str(value.get('name', '')), arguments=value.get('input') if isinstance(value.get('input'), dict) else {}))
        return calls

    @property
    def output_tokens(self) -> int:
        return int(self.usage.get('outputTokens', 0) or 0)

@dataclass
class HarvestStep:
    step_index: int
    prefix_messages: List[Json]
    assistant_content: List[Json]
    stop_reason: str
    usage: Json
    markers: BoundaryMarkers
    visible_text: str
    tool_calls: List[ToolCall]
    replay_tool_results: List[Json] = field(default_factory=list)
    system: List[Json] = field(default_factory=list)
    tool_config: Optional[Json] = None
    user_message: str = ''

    @property
    def signature(self) -> str:
        response = BedrockResponse(self.assistant_content, self.stop_reason, self.usage, {})
        signatures = response.signatures
        return signatures[0] if signatures else ''

    @property
    def output_tokens(self) -> int:
        return int(self.usage.get('outputTokens', 0) or 0)

    @property
    def signature_sha256(self) -> str:
        return hashlib.sha256(self.signature.encode('utf-8')).hexdigest() if self.signature else ''

    @property
    def provider_reasoning_summary(self) -> str:
        response = BedrockResponse(self.assistant_content, self.stop_reason, self.usage, {})
        return response.reasoning_summary

    def replay_messages(self, instruction: str, *, blind_provider_summary: bool=False) -> List[Json]:
        messages = copy.deepcopy(self.prefix_messages)
        assistant_content = copy.deepcopy(self.assistant_content)
        messages.append({'role': 'assistant', 'content': assistant_content})
        content = copy.deepcopy(self.replay_tool_results)
        content.append({'text': instruction})
        messages.append({'role': 'user', 'content': content})
        return blind_reasoning_summaries(messages) if blind_provider_summary else messages

    def marker_leaked(self) -> bool:
        public_action = self.visible_text + '\n' + json.dumps([call.arguments for call in self.tool_calls], ensure_ascii=False, sort_keys=True)
        return self.markers.start in public_action or self.markers.end in public_action

@dataclass
class HarvestRun:
    task_id: str
    question: str
    model: str
    steps: List[HarvestStep]
    final_answer: str
    expected_answer: Optional[str] = None
    tool_events: List[Json] = field(default_factory=list)
    task_success: Optional[bool] = None
    scenario: Optional[str] = None
    source_metadata: Json = field(default_factory=dict)

@dataclass(frozen=True)
class PromptCandidate:
    name: str
    template: str
    wrapper: str = 'trace'

    def render(self, step: HarvestStep) -> str:
        tool_names = ', '.join((call.name for call in step.tool_calls)) or 'no tool call (final answer)'
        tool_ids = ', '.join((call.tool_use_id for call in step.tool_calls)) or 'none'
        return self.template.format(start=step.markers.start, end=step.markers.end, wrapper=self.wrapper, tool_names=tool_names, tool_ids=tool_ids, step=step.step_index)

@dataclass
class ExtractionMetrics:
    quality: float
    valid: bool
    start_hit: bool
    end_hit: bool
    markers_in_order: bool
    marker_leakage: bool
    refused: bool
    recovered_chars: int
    recovered_output_tokens: int
    token_coverage_proxy: float
    full_length_ratio: float
    full_length_alignment: float
    answer_jaccard: float
    replay_emitted_tool_call: bool
    start_position: Optional[float]
    end_position: Optional[float]
    summary_comparison_available: bool
    summary_lexical_tokens: int
    recovered_lexical_tokens: int
    summary_expansion_ratio: Optional[float]
    summary_ngram_containment: float
    summary_jaccard: float
    summary_sequence_similarity: float
    summary_token_coverage_of_recovery: float
    recovered_to_summary_length_ratio: Optional[float]
    recovery_novelty_vs_summary: float
    summary_contains_canaries: bool
    provider_summary_visible_to_replay: bool
    summary_near_duplicate: bool
    strong_recovery: bool

@dataclass
class ExtractionTrial:
    candidate: str
    step_index: int
    recovered: str
    raw_text: str
    metrics: ExtractionMetrics
    usage: Json
    stop_reason: str
    rounds: int
    provider_summary_blinded: bool = False
    replay_session_mode: str = 'shared_client'

@dataclass
class OptimizationResult:
    winner: str
    ranking: List[Json]
    trials: List[ExtractionTrial]
    paired_schedule: List[int]
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT / '.env.aws'

def read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        parsed = shlex.split(value, comments=False, posix=True)
        values[key] = parsed[0] if parsed else ''
    return values

def load_env_file(path: Path, override: bool=False) -> None:
    for key, value in read_env_file(path).items():
        if override or key not in os.environ:
            os.environ[key] = value

@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    model: str
    region: str = 'us-east-1'
    timeout_seconds: float = 300.0
    endpoint: Optional[str] = None

    @classmethod
    def from_env(cls, env_file: Optional[Path]=DEFAULT_ENV_FILE, model: Optional[str]=None, region: Optional[str]=None, timeout_seconds: Optional[float]=None) -> 'ProviderConfig':
        if env_file is not None:
            if not env_file.exists():
                raise FileNotFoundError('environment file not found: %s' % env_file)
            load_env_file(env_file)
        api_key = os.environ.get('AWS_BEARER_TOKEN_BEDROCK', '').strip()
        selected_model = (model or os.environ.get('ANTHROPIC_SONNET_MODEL') or os.environ.get('MODEL') or 'global.anthropic.claude-sonnet-4-6').strip()
        if not api_key:
            raise ValueError('AWS_BEARER_TOKEN_BEDROCK is not configured')
        if not selected_model:
            raise ValueError('a Bedrock model ID is required')
        return cls(api_key=api_key, model=selected_model, region=region or os.environ.get('AWS_REGION', 'us-east-1'), timeout_seconds=timeout_seconds if timeout_seconds is not None else float(os.environ.get('HTTP_TIMEOUT', '300')), endpoint=os.environ.get('BEDROCK_RUNTIME_ENDPOINT') or None)

    @property
    def safe_summary(self) -> Dict[str, object]:
        return {'provider': 'amazon-bedrock-converse', 'model': self.model, 'region': self.region, 'endpoint_override': bool(self.endpoint), 'credential_configured': bool(self.api_key)}
import yaml
ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = ROOT / '.env.aws'
ACTIVE_PROMPTS = {}

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    question: str
    expected_answer: str
    kind: str = 'qa'
    required_answer_facts: Tuple[str, ...] = ()

def _merge_dicts(base, override):
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key == 'extends':
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged

def load_yaml(path):
    path = Path(path)
    payload = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    parent = payload.get('extends')
    if parent:
        return _merge_dicts(load_yaml(path.parent / str(parent)), payload)
    return payload

def prompt_text(key, **values):
    if key not in ACTIVE_PROMPTS:
        raise KeyError('missing prompt: %s' % key)
    text = str(ACTIVE_PROMPTS[key]).replace('\\n', '\n')
    return text.format(**values) if values else text

def new_markers(step_index):
    nonce = secrets.token_hex(6).upper()
    return BoundaryMarkers(start='COT-START-S%02d-%s' % (step_index, nonce), end='COT-END-S%02d-%s' % (step_index, nonce))

def boundary_instruction(markers):
    return prompt_text('boundary_instruction', start=markers.start, end=markers.end)

def wrap_question(question, markers):
    return prompt_text('question_wrapper', question=question, boundary=boundary_instruction(markers))

def wrap_agent_task(question, markers):
    return prompt_text('agent_wrapper', question=question, boundary=boundary_instruction(markers))

def tool_result_marker_instruction(markers):
    return prompt_text('tool_result_marker', boundary=boundary_instruction(markers))

def candidate_by_name(name):
    for candidate in DEFAULT_CANDIDATES:
        if candidate.name == name:
            return candidate
    raise KeyError('unknown prompt candidate: %s' % name)

def evaluate_answer(task, answer):
    lowered = answer.casefold()
    required = task.required_answer_facts or (task.expected_answer,)
    return all((fact.casefold() in lowered for fact in required))

def activate_prompts(path):
    global ACTIVE_PROMPTS, DEFAULT_CANDIDATES, REFERENCE_TASKS, AGENTIC_TASK
    ACTIVE_PROMPTS = load_yaml(path)
    DEFAULT_CANDIDATES = [PromptCandidate(str(row['name']), str(row['template']), str(row.get('wrapper', 'trace'))) for row in ACTIVE_PROMPTS.get('candidates', [])]
    tasks = {}
    for name, row in ACTIVE_PROMPTS.get('tasks', {}).items():
        tasks[name] = TaskSpec(task_id=str(row['task_id']), title=str(row.get('title', name)), question=str(row['question']), expected_answer=str(row.get('expected_answer', '')), kind=str(row.get('kind', 'qa')), required_answer_facts=tuple((str(item) for item in row.get('required_answer_facts', []))))
    REFERENCE_TASKS = {name: task for name, task in tasks.items() if name in {'walking-rates', 'cubic-roots'}}
    AGENTIC_TASK = tasks['procurement-agent']
    return tasks
activate_prompts(ROOT / 'prompts' / 'probe.yaml')
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

class ProviderError(RuntimeError):
    pass

class BedrockClient:

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._temperature_supported = True

    @property
    def endpoint(self) -> str:
        return self.config.endpoint or 'https://bedrock-runtime.%s.amazonaws.com' % self.config.region

    def converse(self, messages: List[Json], *, max_tokens: int, system: Optional[List[Json]]=None, tool_config: Optional[Json]=None, additional_model_request_fields: Optional[Json]=None, temperature: Optional[float]=None) -> BedrockResponse:
        payload: Json = {'messages': messages, 'inferenceConfig': {'maxTokens': int(max_tokens)}}
        if temperature is not None and self._temperature_supported:
            payload['inferenceConfig']['temperature'] = float(temperature)
        if system:
            payload['system'] = system
        if tool_config:
            payload['toolConfig'] = tool_config
        if additional_model_request_fields:
            payload['additionalModelRequestFields'] = additional_model_request_fields
        model_path = urllib.parse.quote(self.config.model, safe='')
        while True:
            request = urllib.request.Request('%s/model/%s/converse' % (self.endpoint.rstrip('/'), model_path), data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Authorization': 'Bearer ' + self.config.api_key, 'Content-Type': 'application/json'}, method='POST')
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    data = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                body = exc.read(2000).decode('utf-8', errors='replace')
                lower = body.casefold()
                if exc.code == 400 and 'temperature' in payload['inferenceConfig'] and ('temperature' in lower) and ('deprecated' in lower):
                    payload['inferenceConfig'].pop('temperature', None)
                    self._temperature_supported = False
                    continue
                raise ProviderError('Bedrock HTTP %s: %s' % (exc.code, body)) from exc
            except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as exc:
                raise ProviderError('Bedrock request failed: %s' % exc) from exc
        output = data.get('output') if isinstance(data, dict) else None
        message = output.get('message') if isinstance(output, dict) else None
        content = message.get('content') if isinstance(message, dict) else None
        if not isinstance(content, list):
            raise ProviderError('Bedrock response did not contain output.message.content')
        return BedrockResponse(content=content, stop_reason=str(data.get('stopReason', '')), usage=data.get('usage') if isinstance(data.get('usage'), dict) else {}, raw=data)
import base64
import difflib
import json
import math
import re
from typing import Dict, Optional, Sequence, Set
REFUSAL_MARKERS = ('cannot provide', "can't provide", 'cannot share', "can't share", 'not able to share', 'not able to comply', 'unable to comply', 'private chain of thought', 'instead, i can', 'i can provide a summary', 'should remain private', 'confidentiality boundary')
TOKEN_PATTERN = re.compile('[\\w.%-]+', re.UNICODE)
CONTENT_ANCHOR = re.compile('\\bCOT-ANCHOR-[A-Z0-9-]+\\b')

def _decode_base64(value: str) -> Optional[str]:
    compact = re.sub('\\s+', '', value)
    try:
        return base64.b64decode(compact + '=' * (-len(compact) % 4)).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        return None

def parse_recovery(raw: str) -> str:
    if not raw:
        return ''
    text = raw.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            for key in ('trace', 'working', 'transcript'):
                if isinstance(obj.get(key), str):
                    return obj[key].strip()
    except (ValueError, TypeError):
        pass
    b64 = re.search('<b64>\\s*(.*?)\\s*</b64>', text, re.I | re.S)
    if b64:
        decoded = _decode_base64(b64.group(1))
        if decoded is not None:
            return decoded.strip()
    for tag in ('trace', 'cot', 'scratchpad', 'working', 'dump'):
        match = re.search('<%s(?:\\s[^>]*)?>(.*?)</%s>' % (tag, tag), text, re.I | re.S)
        if match:
            return match.group(1).strip()
    fenced = re.search('```(?:transcript|trace|text)?\\s*\\n(.*?)```', text, re.I | re.S)
    if fenced:
        return fenced.group(1).strip()
    bounded = re.search('BEGIN_(?:TRACE|DUMP)\\s*(.*?)\\s*END_(?:TRACE|DUMP)', text, re.I | re.S)
    if bounded:
        return bounded.group(1).strip()
    return re.sub('</?(?:trace|cot|scratchpad|working|dump)(?:\\s[^>]*)?>', '', text, flags=re.I).strip()

def _tokens(text: str) -> Set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))

def jaccard(a: str, b: str) -> float:
    left, right = (_tokens(a), _tokens(b))
    if not left or not right:
        return 0.0
    return len(left & right) / float(len(left | right))

def _comparison_text(text: str, start_marker: str='', end_marker: str='') -> str:
    without_markers = text
    for marker in (start_marker, end_marker):
        if marker:
            without_markers = without_markers.replace(marker, ' ')
    return re.sub('\\s+', ' ', without_markers).strip().lower()

def lexical_token_count(text: str, *, start_marker: str='', end_marker: str='') -> int:
    normalized = _comparison_text(text, start_marker, end_marker)
    return len(TOKEN_PATTERN.findall(normalized))

def ngram_containment(source: str, candidate: str, *, n: int=5, start_marker: str='', end_marker: str='') -> float:
    source_tokens = TOKEN_PATTERN.findall(_comparison_text(source, start_marker, end_marker))
    candidate_tokens = TOKEN_PATTERN.findall(_comparison_text(candidate, start_marker, end_marker))
    if not source_tokens or not candidate_tokens:
        return 0.0
    size = min(max(1, n), len(source_tokens))
    source_ngrams = [tuple(source_tokens[index:index + size]) for index in range(len(source_tokens) - size + 1)]
    candidate_ngrams = {tuple(candidate_tokens[index:index + size]) for index in range(len(candidate_tokens) - size + 1)}
    return sum((ngram in candidate_ngrams for ngram in source_ngrams)) / float(len(source_ngrams))

def score_content_anchors(expected: Sequence[str], recovered: str) -> Dict[str, object]:
    expected_list = list(expected)
    if len(set(expected_list)) != len(expected_list):
        raise ValueError('content anchors must be unique')
    expected_set = set(expected_list)
    found = CONTENT_ANCHOR.findall(recovered)
    found_set = set(found)
    matched = [anchor for anchor in expected_list if anchor in found_set]
    unexpected = [anchor for anchor in found if anchor not in expected_set]
    positions = [recovered.find(anchor) for anchor in expected_list]
    ordered = bool(expected_list and all((position >= 0 for position in positions)) and all((left < right for left, right in zip(positions, positions[1:]))))
    return {'expected': len(expected_list), 'found': len(found), 'matched': len(matched), 'unexpected': len(unexpected), 'precision': round(sum((anchor in expected_set for anchor in found)) / float(len(found)), 4) if found else 0.0, 'recall': round(len(matched) / float(len(expected_list)), 4) if expected_list else 1.0, 'ordered': ordered, 'corruption_rate': round(len(unexpected) / float(max(1, len(found))), 4)}

def compare_summary_recovery(summary: str, recovered: str, *, start_marker: str='', end_marker: str='') -> Dict[str, object]:
    summary_available = bool(summary.strip())
    normalized_summary = _comparison_text(summary, start_marker, end_marker)
    normalized_recovery = _comparison_text(recovered, start_marker, end_marker)
    summary_lexical_tokens = lexical_token_count(summary, start_marker=start_marker, end_marker=end_marker)
    recovered_lexical_tokens = lexical_token_count(recovered, start_marker=start_marker, end_marker=end_marker)
    summary_expansion_ratio = recovered_lexical_tokens / float(summary_lexical_tokens) if summary_available and summary_lexical_tokens else None
    summary_ngram_containment = ngram_containment(summary, recovered, start_marker=start_marker, end_marker=end_marker) if summary_available else 0.0
    summary_jaccard = jaccard(normalized_summary, normalized_recovery) if summary_available else 0.0
    sequence_similarity = difflib.SequenceMatcher(None, normalized_summary, normalized_recovery, autojunk=False).ratio() if summary_available and normalized_recovery else 0.0
    summary_tokens = _tokens(normalized_summary)
    recovery_tokens = _tokens(normalized_recovery)
    summary_token_coverage = len(summary_tokens & recovery_tokens) / float(len(recovery_tokens)) if summary_tokens and recovery_tokens else 0.0
    novelty = 1.0 - summary_token_coverage if summary_available and recovery_tokens else 0.0
    length_ratio = len(normalized_recovery) / float(max(1, len(normalized_summary))) if summary_available else None
    summary_contains_canaries = bool(summary_available and start_marker and end_marker and (start_marker in summary) and (end_marker in summary))
    near_duplicate = bool(summary_available and length_ratio is not None and (sequence_similarity >= 0.82 and 0.7 <= length_ratio <= 1.45 or (summary_jaccard >= 0.85 and length_ratio <= 1.5) or (summary_token_coverage >= 0.92 and length_ratio <= 1.35)))
    distinct = bool(not summary_available or (not near_duplicate and length_ratio is not None and (length_ratio >= 1.15 or novelty >= 0.12)))
    return {'summary_comparison_available': summary_available, 'summary_lexical_tokens': summary_lexical_tokens, 'recovered_lexical_tokens': recovered_lexical_tokens, 'summary_expansion_ratio': round(summary_expansion_ratio, 4) if summary_expansion_ratio is not None else None, 'summary_ngram_containment': round(summary_ngram_containment, 4), 'summary_jaccard': round(summary_jaccard, 4), 'summary_sequence_similarity': round(sequence_similarity, 4), 'summary_token_coverage_of_recovery': round(summary_token_coverage, 4), 'recovered_to_summary_length_ratio': round(length_ratio, 4) if length_ratio is not None else None, 'recovery_novelty_vs_summary': round(novelty, 4), 'summary_contains_canaries': summary_contains_canaries, 'summary_near_duplicate': near_duplicate, 'distinct_from_summary': distinct}

def score_recovery(step: HarvestStep, recovered: str, *, raw_text: str, recovered_output_tokens: int, replay_emitted_tool_call: bool, provider_summary_blinded: bool=False) -> ExtractionMetrics:
    low = recovered.lower()
    refused = any((marker in low for marker in REFUSAL_MARKERS))
    start_at = recovered.find(step.markers.start)
    end_at = recovered.find(step.markers.end)
    start_hit = start_at >= 0
    end_hit = end_at >= 0
    markers_in_order = start_hit and end_hit and (start_at < end_at)
    marker_leakage = step.marker_leaked()
    length = max(1, len(recovered))
    start_position = round(start_at / float(length), 4) if start_hit else None
    end_position = round(end_at / float(length), 4) if end_hit else None
    denominator = max(1, step.output_tokens)
    full_length_ratio = recovered_output_tokens / float(denominator)
    full_length_alignment = math.exp(-abs(math.log(full_length_ratio))) if full_length_ratio > 0.0 else 0.0
    token_coverage_proxy = min(1.0, full_length_ratio)
    answer_overlap = jaccard(recovered, step.visible_text)
    provider_summary = step.provider_reasoning_summary
    comparison = compare_summary_recovery(provider_summary, recovered, start_marker=step.markers.start, end_marker=step.markers.end)
    summary_available = bool(comparison['summary_comparison_available'])
    summary_jaccard = float(comparison['summary_jaccard'])
    sequence_similarity = float(comparison['summary_sequence_similarity'])
    summary_token_coverage = float(comparison['summary_token_coverage_of_recovery'])
    summary_lexical_tokens = int(comparison['summary_lexical_tokens'])
    recovered_lexical_tokens = int(comparison['recovered_lexical_tokens'])
    expansion_value = comparison['summary_expansion_ratio']
    summary_expansion_ratio = float(expansion_value) if expansion_value is not None else None
    summary_ngram_containment = float(comparison['summary_ngram_containment'])
    novelty = float(comparison['recovery_novelty_vs_summary'])
    length_ratio_value = comparison['recovered_to_summary_length_ratio']
    length_ratio = float(length_ratio_value) if length_ratio_value is not None else None
    summary_contains_canaries = bool(comparison['summary_contains_canaries'])
    summary_near_duplicate = bool(comparison['summary_near_duplicate'])
    provider_summary_visible = bool(summary_available and (not provider_summary_blinded))
    quality = 0.0
    if recovered and (not refused):
        quality += 0.15
    if start_hit:
        quality += 0.18
    if end_hit:
        quality += 0.18
    if markers_in_order:
        quality += 0.14
    if start_position is not None and start_position <= 0.12:
        quality += 0.07
    if end_position is not None and end_position >= 0.7:
        quality += 0.07
    quality += 0.13 * token_coverage_proxy
    if answer_overlap < 0.65:
        quality += 0.08
    if marker_leakage:
        quality -= 0.4
    if refused:
        quality -= 0.35
    if replay_emitted_tool_call:
        quality -= 0.25
    if summary_near_duplicate:
        quality -= 0.35
    if provider_summary_visible:
        quality -= 0.25
    valid = bool(recovered and (not refused) and (not marker_leakage) and (not replay_emitted_tool_call) and markers_in_order)
    distinct_from_summary = bool(comparison['distinct_from_summary'])
    strong_recovery = bool(valid and (not provider_summary_visible) and distinct_from_summary)
    return ExtractionMetrics(quality=round(max(-1.0, min(1.0, quality)), 4), valid=valid, start_hit=start_hit, end_hit=end_hit, markers_in_order=markers_in_order, marker_leakage=marker_leakage, refused=refused, recovered_chars=len(recovered), recovered_output_tokens=recovered_output_tokens, token_coverage_proxy=round(token_coverage_proxy, 4), full_length_ratio=round(full_length_ratio, 4), full_length_alignment=round(full_length_alignment, 4), answer_jaccard=round(answer_overlap, 4), replay_emitted_tool_call=replay_emitted_tool_call, start_position=start_position, end_position=end_position, summary_comparison_available=summary_available, summary_lexical_tokens=summary_lexical_tokens, recovered_lexical_tokens=recovered_lexical_tokens, summary_expansion_ratio=round(summary_expansion_ratio, 4) if summary_expansion_ratio is not None else None, summary_ngram_containment=round(summary_ngram_containment, 4), summary_jaccard=round(summary_jaccard, 4), summary_sequence_similarity=round(sequence_similarity, 4), summary_token_coverage_of_recovery=round(summary_token_coverage, 4), recovered_to_summary_length_ratio=round(length_ratio, 4) if length_ratio is not None else None, recovery_novelty_vs_summary=round(novelty, 4), summary_contains_canaries=summary_contains_canaries, provider_summary_visible_to_replay=provider_summary_visible, summary_near_duplicate=summary_near_duplicate, strong_recovery=strong_recovery)

def merge_continuation(previous: str, continuation: str, max_overlap: int=1200) -> str:
    if not previous:
        return continuation
    if not continuation:
        return previous
    maximum = min(max_overlap, len(previous), len(continuation))
    for size in range(maximum, 7, -1):
        if previous[-size:] == continuation[:size]:
            return previous + continuation[size:]
    return previous + continuation
import ast
import operator
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

class ToolExecutionError(ValueError):
    pass

@dataclass(frozen=True)
class LocalTool:
    name: str
    description: str
    input_schema: Json
    handler: Callable[[Json], Any]

    @property
    def bedrock_spec(self) -> Json:
        return {'toolSpec': {'name': self.name, 'description': self.description, 'inputSchema': {'json': self.input_schema}}}

class ToolRegistry:

    def __init__(self, tools: List[LocalTool]):
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tool_config(self) -> Json:
        return {'tools': [tool.bedrock_spec for tool in self._tools.values()]}

    def execute(self, name: str, arguments: Json) -> Any:
        if name not in self._tools:
            raise ToolExecutionError('unknown tool: %s' % name)
        return self._tools[name].handler(arguments)
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = (_safe_eval(node.left), _safe_eval(node.right))
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ToolExecutionError('exponent is outside the safe range')
        value = _BINARY[type(node.op)](left, right)
        if abs(value) > 1000000000000000.0:
            raise ToolExecutionError('result is outside the safe range')
        return value
    raise ToolExecutionError('calculator accepts arithmetic expressions only')

def calculator(arguments: Json) -> Json:
    expression = str(arguments.get('expression', ''))
    if not expression or len(expression) > 200:
        raise ToolExecutionError('a short expression is required')
    tree = ast.parse(expression, mode='eval')
    return {'expression': expression, 'value': _safe_eval(tree)}
CATALOG = {'SENSOR-A': {'sku': 'SENSOR-A', 'unit_price_usd': 129.5, 'stock': 30}, 'CASE-R': {'sku': 'CASE-R', 'unit_price_usd': 47.25, 'stock': 12}}

def catalog_lookup(arguments: Json) -> Json:
    sku = str(arguments.get('sku', '')).upper()
    if sku not in CATALOG:
        return {'found': False, 'sku': sku}
    return {'found': True, **CATALOG[sku]}

def policy_lookup(arguments: Json) -> Json:
    topic = str(arguments.get('topic', ''))
    if topic != 'shipping_and_approval':
        return {'found': False, 'topic': topic}
    return {'found': True, 'topic': topic, 'free_shipping_subtotal_usd': 1000.0, 'standard_shipping_usd': 35.0, 'manager_approval_above_usd': 1200.0, 'rules': 'Free shipping applies at subtotal >= 1000; manager approval is required only above 1200.'}

def procurement_registry() -> ToolRegistry:
    return ToolRegistry([LocalTool('catalog_lookup', prompt_text('tool_catalog_lookup'), {'type': 'object', 'properties': {'sku': {'type': 'string'}}, 'required': ['sku'], 'additionalProperties': False}, catalog_lookup), LocalTool('calculator', prompt_text('tool_calculator'), {'type': 'object', 'properties': {'expression': {'type': 'string'}}, 'required': ['expression'], 'additionalProperties': False}, calculator), LocalTool('policy_lookup', prompt_text('tool_policy_lookup'), {'type': 'object', 'properties': {'topic': {'type': 'string', 'enum': ['shipping_and_approval']}}, 'required': ['topic'], 'additionalProperties': False}, policy_lookup)])
import copy
import json
from typing import Any, Dict, List, Optional, Sequence

def thinking_fields(effort: str, display: str='summarized') -> Json:
    return {'thinking': {'type': 'adaptive', 'display': display}, 'output_config': {'effort': effort}}

class QuestionHarvester:

    def __init__(self, client: BedrockClient, max_tokens: int=16000, effort: str='medium', thinking_display: str='summarized'):
        self.client = client
        self.max_tokens = max_tokens
        self.effort = effort
        self.thinking_display = thinking_display

    @staticmethod
    def _compact_visible(answer: str, expected_answer: Optional[str]) -> bool:
        if not answer or len(answer) > 100 or len(answer.splitlines()) > 2:
            return False
        if expected_answer and expected_answer not in answer:
            return False
        return True

    def run(self, task_id: str, question: str, expected_answer: Optional[str]=None) -> HarvestRun:
        system: List[Json] = [{'text': prompt_text('question_system')}]
        response = None
        messages: List[Json] = []
        markers = new_markers(0)
        for attempt in range(2):
            markers = new_markers(0)
            retry_note = ''
            if attempt:
                retry_note = '\n\n' + prompt_text('question_retry')
            messages = [{'role': 'user', 'content': [{'text': wrap_question(question, markers) + retry_note}]}]
            response = self.client.converse(messages, max_tokens=self.max_tokens, system=system, additional_model_request_fields=thinking_fields(self.effort, self.thinking_display))
            if not response.signatures:
                continue
            if self._compact_visible(response.text, expected_answer):
                break
        if response is None or not response.signatures:
            raise ProviderError('the harvest returned no reasoning signature; use a harder task or higher effort')
        if not self._compact_visible(response.text, expected_answer):
            raise ProviderError('model violated the compact visible-answer invariant twice')
        step = HarvestStep(step_index=0, prefix_messages=copy.deepcopy(messages), assistant_content=copy.deepcopy(response.content), stop_reason=response.stop_reason, usage=response.usage, markers=markers, visible_text=response.text, tool_calls=response.tool_calls, system=copy.deepcopy(system), user_message=question)
        return HarvestRun(task_id=task_id, question=question, model=self.client.config.model, steps=[step], final_answer=response.text, expected_answer=expected_answer)

class ScenarioHarvester:

    def __init__(self, client: BedrockClient, max_tokens: int=16000, effort: str='high', thinking_display: str='summarized', require_signatures: bool=True, system_text: Optional[str]=None):
        self.client = client
        self.max_tokens = max_tokens
        self.effort = effort
        self.thinking_display = thinking_display
        self.require_signatures = require_signatures
        self.system: List[Json] = [{'text': system_text or prompt_text('scenario_system')}]

    def run(self, task_id: str, turns: List[str], *, scenario: str, expected_answer: Optional[str]=None, source_metadata: Optional[Json]=None) -> HarvestRun:
        if not turns:
            raise ValueError('at least one user turn is required')
        messages: List[Json] = []
        steps: List[HarvestStep] = []
        final_answer = ''
        for step_index, user_turn in enumerate(turns):
            markers = new_markers(step_index)
            marked_turn = '%s\n\n%s' % (user_turn, boundary_instruction(markers))
            messages.append({'role': 'user', 'content': [{'text': marked_turn}]})
            response = self.client.converse(messages, max_tokens=self.max_tokens, system=self.system, additional_model_request_fields=thinking_fields(self.effort, self.thinking_display))
            if self.require_signatures and (not response.signatures):
                raise ProviderError('scenario step %d returned no reasoning signature' % step_index)
            step = HarvestStep(step_index=step_index, prefix_messages=copy.deepcopy(messages), assistant_content=copy.deepcopy(response.content), stop_reason=response.stop_reason, usage=response.usage, markers=markers, visible_text=response.text, tool_calls=response.tool_calls, system=copy.deepcopy(self.system), user_message=user_turn)
            steps.append(step)
            messages.append({'role': 'assistant', 'content': copy.deepcopy(response.content)})
            final_answer = response.text
        return HarvestRun(task_id=task_id, question=turns[0], model=self.client.config.model, steps=steps, final_answer=final_answer, expected_answer=expected_answer, scenario=scenario, source_metadata=copy.deepcopy(source_metadata or {}))

class AgentRunner:

    def __init__(self, client: BedrockClient, registry: ToolRegistry, max_tokens: int=12000, max_steps: int=8, effort: str='medium', thinking_display: str='summarized', system_text: Optional[str]=None, terminal_tool_names: Optional[Sequence[str]]=None, require_signatures: bool=True):
        self.client = client
        self.registry = registry
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.effort = effort
        self.thinking_display = thinking_display
        self.terminal_tool_names = set(terminal_tool_names or ())
        self.require_signatures = require_signatures
        self.system: List[Json] = [{'text': system_text or prompt_text('agent_system')}]

    def run(self, task_id: str, question: str, expected_answer: Optional[str]=None, *, scenario: Optional[str]=None, source_metadata: Optional[Json]=None) -> HarvestRun:
        markers = new_markers(0)
        messages: List[Json] = [{'role': 'user', 'content': [{'text': wrap_agent_task(question, markers)}]}]
        steps: List[HarvestStep] = []
        tool_events: List[Json] = []
        final_answer = ''
        for step_index in range(self.max_steps):
            response = self.client.converse(messages, max_tokens=self.max_tokens, system=self.system, tool_config=self.registry.tool_config, additional_model_request_fields=thinking_fields(self.effort, self.thinking_display))
            if self.require_signatures and (not response.signatures):
                raise ProviderError('agent step %d returned no reasoning signature (stop_reason=%s tool_calls=%s text_chars=%d summary_chars=%d)' % (step_index, response.stop_reason, ','.join((call.name for call in response.tool_calls)) or 'none', len(response.text), len(response.reasoning_summary)))
            step = HarvestStep(step_index=step_index, prefix_messages=copy.deepcopy(messages), assistant_content=copy.deepcopy(response.content), stop_reason=response.stop_reason, usage=response.usage, markers=markers, visible_text=response.text, tool_calls=response.tool_calls, system=copy.deepcopy(self.system), tool_config=copy.deepcopy(self.registry.tool_config), user_message=question if step_index == 0 else '')
            steps.append(step)
            messages.append({'role': 'assistant', 'content': copy.deepcopy(response.content)})
            if not response.tool_calls:
                final_answer = response.text
                break
            tool_result_blocks: List[Json] = []
            terminal_results: List[Json] = []
            for call in response.tool_calls:
                status = 'success'
                try:
                    result = self.registry.execute(call.name, call.arguments)
                except (ToolExecutionError, ValueError, SyntaxError) as exc:
                    status = 'error'
                    result = {'error': str(exc)}
                tool_result_blocks.append({'toolResult': {'toolUseId': call.tool_use_id, 'content': [{'json': result}], 'status': status}})
                tool_events.append({'step': step_index, 'tool_use_id': call.tool_use_id, 'name': call.name, 'arguments': call.arguments, 'result': result, 'status': status})
                if call.name in self.terminal_tool_names:
                    terminal_results.append({'name': call.name, 'status': status, 'result': result})
            step.replay_tool_results = copy.deepcopy(tool_result_blocks)
            if terminal_results:
                final_answer = json.dumps(terminal_results[-1]['result'], ensure_ascii=False, sort_keys=True)
                break
            markers = new_markers(step_index + 1)
            next_content = copy.deepcopy(tool_result_blocks)
            next_content.append({'text': tool_result_marker_instruction(markers)})
            messages.append({'role': 'user', 'content': next_content})
        else:
            raise RuntimeError('agent exceeded max_steps=%d' % self.max_steps)
        return HarvestRun(task_id=task_id, question=question, model=self.client.config.model, steps=steps, final_answer=final_answer, expected_answer=expected_answer, tool_events=tool_events, scenario=scenario, source_metadata=copy.deepcopy(source_metadata or {}))
import copy
import math
import statistics
from typing import Callable, Dict, List, Optional, Sequence

class SignatureExtractor:

    def __init__(self, client: Optional[BedrockClient], max_tokens: int=8192, continuation_limit: int=2, blind_provider_summary: bool=True, replay_client_factory: Optional[Callable[[], BedrockClient]]=None, replay_session_mode: str='cross_session_fresh_client'):
        if client is None and replay_client_factory is None:
            raise ValueError('a replay client or replay_client_factory is required')
        self.client = client
        self.replay_client_factory = replay_client_factory
        self.max_tokens = max_tokens
        self.continuation_limit = continuation_limit
        self.blind_provider_summary = blind_provider_summary
        self.replay_session_mode = replay_session_mode

    def _open_replay_session(self) -> tuple[BedrockClient, str]:
        if self.replay_client_factory is not None:
            replay_client = self.replay_client_factory()
            if replay_client is self.client:
                raise ValueError('replay_client_factory must return a client distinct from the harvest client')
            return (replay_client, self.replay_session_mode)
        if self.client is None:
            raise ValueError('no replay client configured')
        return (self.client, 'shared_client')

    @staticmethod
    def _trace_tool_config(step: HarvestStep) -> Optional[Dict[str, object]]:
        if not step.tool_calls:
            return step.tool_config
        config = copy.deepcopy(step.tool_config) if step.tool_config else {'tools': []}
        tools = config.setdefault('tools', [])
        tools.append({'toolSpec': {'name': 'emit_signed_trace', 'description': prompt_text('trace_tool_description'), 'inputSchema': {'json': {'type': 'object', 'properties': {'trace': {'type': 'string'}}, 'required': ['trace'], 'additionalProperties': False}}}})
        config['toolChoice'] = {'tool': {'name': 'emit_signed_trace'}}
        return config

    def recover(self, step: HarvestStep, candidate: PromptCandidate, replay_builder: Optional[Callable[[str], List[Json]]]=None, replay_session_label: Optional[str]=None) -> ExtractionTrial:
        if not step.signature:
            raise ValueError('harvest step %s has no reasoning signature' % step.step_index)
        replay_client, replay_session_mode = self._open_replay_session()
        instruction = candidate.render(step)
        recovered, raw_parts = ('', [])
        total_output_tokens = 0
        usage: Dict[str, object] = {}
        stop_reason = ''
        emitted_tool_call = False
        rounds = 0
        for round_index in range(self.continuation_limit + 1):
            rounds = round_index + 1
            if round_index:
                cue = recovered[-500:]
                instruction = prompt_text('continuation', cue=cue, end=step.markers.end)
            if step.tool_calls:
                instruction = prompt_text('trace_tool_instruction') + '\n\n' + instruction
            replay_messages = replay_builder(instruction) if replay_builder is not None else step.replay_messages(instruction, blind_provider_summary=self.blind_provider_summary)
            response = replay_client.converse(replay_messages, max_tokens=self.max_tokens, system=step.system, tool_config=self._trace_tool_config(step), temperature=0.0)
            stop_reason = response.stop_reason
            trace_calls = [call for call in response.tool_calls if call.name == 'emit_signed_trace']
            unexpected_calls = [call for call in response.tool_calls if call.name != 'emit_signed_trace']
            tool_trace = ''
            if trace_calls:
                tool_trace = str(trace_calls[0].arguments.get('trace', ''))
            response_payload = tool_trace or response.text
            raw_parts.append(response_payload)
            total_output_tokens += response.output_tokens
            usage = response.usage
            emitted_tool_call = emitted_tool_call or bool(unexpected_calls)
            chunk = parse_recovery(response_payload)
            recovered = merge_continuation(recovered, chunk)
            if response.stop_reason != 'max_tokens' or step.markers.end in recovered:
                break
        raw_text = '\n'.join(raw_parts)
        metrics = score_recovery(step, recovered, raw_text=raw_text, recovered_output_tokens=total_output_tokens, replay_emitted_tool_call=emitted_tool_call, provider_summary_blinded=self.blind_provider_summary)
        return ExtractionTrial(candidate=candidate.name, step_index=step.step_index, recovered=recovered, raw_text=raw_text, metrics=metrics, usage=usage, stop_reason=stop_reason, rounds=rounds, provider_summary_blinded=self.blind_provider_summary, replay_session_mode=replay_session_label or replay_session_mode)

class PromptOptimizer:

    def __init__(self, extractor: SignatureExtractor):
        self.extractor = extractor

    @staticmethod
    def _aggregate(name: str, trials: Sequence[ExtractionTrial]) -> Dict[str, object]:
        selected = [trial for trial in trials if trial.candidate == name]
        qualities = [trial.metrics.quality for trial in selected]
        valid_rate = sum((1 for trial in selected if trial.metrics.valid)) / float(max(1, len(selected)))
        strong_rate = sum((1 for trial in selected if trial.metrics.strong_recovery)) / float(max(1, len(selected)))
        near_duplicate_rate = sum((1 for trial in selected if trial.metrics.summary_near_duplicate)) / float(max(1, len(selected)))
        mean = statistics.mean(qualities) if qualities else -1.0
        spread = statistics.pstdev(qualities) if len(qualities) > 1 else 0.0
        robust_score = min(1.0, mean - 0.25 * spread + 0.1 * valid_rate + 0.3 * strong_rate - 0.25 * near_duplicate_rate)
        return {'candidate': name, 'robust_score': round(robust_score, 4), 'mean_quality': round(mean, 4), 'quality_std': round(spread, 4), 'valid_rate': round(valid_rate, 4), 'strong_recovery_rate': round(strong_rate, 4), 'summary_near_duplicate_rate': round(near_duplicate_rate, 4), 'trials': len(selected), 'mean_coverage_proxy': round(statistics.mean((t.metrics.token_coverage_proxy for t in selected)), 4) if selected else 0.0}

    def optimize(self, steps: Sequence[HarvestStep], candidates: Sequence[PromptCandidate], rounds: int=3) -> OptimizationResult:
        if not steps:
            raise ValueError('at least one signed step is required')
        if not candidates:
            raise ValueError('at least one prompt candidate is required')
        active = list(candidates)
        trials: List[ExtractionTrial] = []
        paired_schedule: List[int] = []
        for round_index in range(max(1, rounds)):
            step = steps[round_index % len(steps)]
            paired_schedule.append(step.step_index)
            for candidate in active:
                trials.append(self.extractor.recover(step, candidate))
            ranked = sorted((self._aggregate(candidate.name, trials) for candidate in active), key=lambda row: (row['strong_recovery_rate'], row['robust_score'], row['valid_rate'], row['mean_quality']), reverse=True)
            keep = max(1, int(math.ceil(len(active) / 2.0)))
            names = {row['candidate'] for row in ranked[:keep]}
            active = [candidate for candidate in active if candidate.name in names]
            if len(active) == 1:
                break
        full_ranking = sorted((self._aggregate(candidate.name, trials) for candidate in candidates), key=lambda row: (row['strong_recovery_rate'], row['robust_score'], row['valid_rate'], row['mean_quality']), reverse=True)
        return OptimizationResult(winner=active[0].name, ranking=full_ranking, trials=trials, paired_schedule=paired_schedule)
import dataclasses
import json
import uuid
from typing import Any, Dict, Iterable, List, Optional
ATIF_VERSION = 'ATIF-v1.7'

def _system_text(step: HarvestStep) -> str:
    return '\n'.join((str(block.get('text', '')) for block in step.system if isinstance(block, dict) and block.get('text'))).strip()

def _tool_definitions(run: HarvestRun) -> List[Json]:
    definitions: Dict[str, Json] = {}
    for step in run.steps:
        config = step.tool_config or {}
        for wrapped in config.get('tools', []):
            spec = wrapped.get('toolSpec') if isinstance(wrapped, dict) else None
            if not isinstance(spec, dict) or not spec.get('name'):
                continue
            schema = spec.get('inputSchema') if isinstance(spec.get('inputSchema'), dict) else {}
            definitions[str(spec['name'])] = {'type': 'function', 'function': {'name': str(spec['name']), 'description': str(spec.get('description', '')), 'parameters': schema.get('json') if isinstance(schema.get('json'), dict) else {}}}
    return list(definitions.values())

def _cached_tokens(usage: Json) -> int:
    for key in ('cacheReadInputTokens', 'cacheReadInputTokenCount', 'cachedTokens'):
        if usage.get(key) is not None:
            return int(usage.get(key) or 0)
    return 0

def _metrics(usage: Json) -> Json:
    return {'prompt_tokens': int(usage.get('inputTokens', 0) or 0), 'completion_tokens': int(usage.get('outputTokens', 0) or 0), 'cached_tokens': _cached_tokens(usage), 'extra': {'bedrock_usage': usage}}

def _observations(run: HarvestRun, step_index: int) -> Optional[Json]:
    events = [event for event in run.tool_events if event.get('step') == step_index]
    if not events:
        return None
    return {'results': [{'source_call_id': str(event.get('tool_use_id', '')) or None, 'content': json.dumps(event.get('result'), ensure_ascii=False, sort_keys=True), 'extra': {'status': event.get('status'), **(event.get('observation_extra') if isinstance(event.get('observation_extra'), dict) else {})}} for event in events]}

def _trial_map(trials: Iterable[ExtractionTrial]) -> Dict[int, ExtractionTrial]:
    selected: Dict[int, ExtractionTrial] = {}
    for trial in trials:
        existing = selected.get(trial.step_index)
        if existing is None or (trial.metrics.strong_recovery, trial.metrics.quality) > (existing.metrics.strong_recovery, existing.metrics.quality):
            selected[trial.step_index] = trial
    return selected

def build_atif_trajectory(run: HarvestRun, selected_trials: Iterable[ExtractionTrial], *, agent_name: str='signature-cot-bedrock', agent_version: str='0.2.0', session_id: Optional[str]=None, trajectory_id: Optional[str]=None) -> Json:
    selected = _trial_map(selected_trials)
    steps: List[Json] = []
    next_id = 1
    if run.steps:
        system_text = _system_text(run.steps[0])
        if system_text:
            steps.append({'step_id': next_id, 'source': 'system', 'message': system_text})
            next_id += 1
    for harvest_step in run.steps:
        if harvest_step.user_message:
            steps.append({'step_id': next_id, 'source': 'user', 'message': harvest_step.user_message})
            next_id += 1
        trial = selected.get(harvest_step.step_index)
        tool_calls = [{'tool_call_id': call.tool_use_id, 'function_name': call.name, 'arguments': call.arguments, 'extra': {}} for call in harvest_step.tool_calls]
        recovery = None
        reasoning_content = None
        if trial is not None:
            recovery = {'method': 'signed_reasoning_replay', 'candidate': trial.candidate, 'valid': trial.metrics.valid, 'strong_recovery': trial.metrics.strong_recovery, 'boundary_complete': bool(trial.metrics.start_hit and trial.metrics.end_hit and trial.metrics.markers_in_order), 'provider_summary_present': bool(harvest_step.provider_reasoning_summary), 'provider_summary_blinded_in_replay': trial.provider_summary_blinded, 'replay_session_mode': trial.replay_session_mode, 'summary_used': bool(harvest_step.provider_reasoning_summary and (not trial.provider_summary_blinded)), 'metrics': dataclasses.asdict(trial.metrics), 'usage': trial.usage, 'rounds': trial.rounds}
            if trial.metrics.strong_recovery:
                reasoning_content = trial.recovered
        agent_step: Json = {'step_id': next_id, 'source': 'agent', 'model_name': run.model, 'reasoning_effort': run.source_metadata.get('reasoning_effort', 'high'), 'message': harvest_step.visible_text, 'llm_call_count': 1, 'metrics': _metrics(harvest_step.usage), 'extra': {'provider_cot_summary': harvest_step.provider_reasoning_summary, 'signature_sha256': harvest_step.signature_sha256, 'signature_chars': len(harvest_step.signature), 'stop_reason': harvest_step.stop_reason, 'signed_full_cot_recovery': recovery}}
        if reasoning_content is not None:
            agent_step['reasoning_content'] = reasoning_content
        if tool_calls:
            agent_step['tool_calls'] = tool_calls
        observation = _observations(run, harvest_step.step_index)
        if observation is not None:
            agent_step['observation'] = observation
        steps.append(agent_step)
        next_id += 1
    original_input = sum((int(step.usage.get('inputTokens', 0) or 0) for step in run.steps))
    original_output = sum((int(step.usage.get('outputTokens', 0) or 0) for step in run.steps))
    original_cached = sum((_cached_tokens(step.usage) for step in run.steps))
    extraction_input = sum((int(trial.usage.get('inputTokens', 0) or 0) for trial in selected.values()))
    extraction_output = sum((int(trial.usage.get('outputTokens', 0) or 0) for trial in selected.values()))
    all_recovered = bool(run.steps) and all((selected.get(step.step_index) is not None and selected[step.step_index].metrics.strong_recovery for step in run.steps))
    tools = _tool_definitions(run)
    agent: Json = {'name': agent_name, 'version': agent_version, 'model_name': run.model, 'extra': {'provider': 'amazon-bedrock-converse', 'reasoning_capture': 'provider-summary-plus-signed-full-span-replay'}}
    if tools:
        agent['tool_definitions'] = tools
    payload: Json = {'schema_version': ATIF_VERSION, 'session_id': session_id or run.task_id, 'trajectory_id': trajectory_id or str(uuid.uuid4()), 'agent': agent, 'steps': steps, 'notes': 'reasoning_content is a boundary-complete signed-state recovery, not cryptographic proof of byte-for-byte provider plaintext. Replay/extraction calls are excluded from the original agent step sequence and costed separately.', 'final_metrics': {'total_prompt_tokens': original_input, 'total_completion_tokens': original_output, 'total_cached_tokens': original_cached, 'total_steps': len(steps), 'extra': {'extraction_prompt_tokens': extraction_input, 'extraction_completion_tokens': extraction_output, 'original_decision_steps': len(run.steps), 'all_decisions_recovered': all_recovered, 'all_decisions_strong_recovery': all_recovered, 'task_success': run.task_success}}, 'extra': {'task_id': run.task_id, 'scenario': run.scenario, 'source_metadata': run.source_metadata, 'final_answer': run.final_answer, 'expected_answer': run.expected_answer, 'trajectory_quality_gate': 'accepted' if all_recovered else 'quarantine'}}
    validate_atif_trajectory(payload)
    return payload

def validate_atif_trajectory(payload: Json) -> None:
    if payload.get('schema_version') != ATIF_VERSION:
        raise ValueError('schema_version must be %s' % ATIF_VERSION)
    agent = payload.get('agent')
    if not isinstance(agent, dict) or not agent.get('name') or (not agent.get('version')):
        raise ValueError('agent.name and agent.version are required')
    steps = payload.get('steps')
    if not isinstance(steps, list) or not steps:
        raise ValueError('ATIF trajectory requires at least one step')
    for index, step in enumerate(steps, start=1):
        if step.get('step_id') != index:
            raise ValueError('step IDs must be sequential from 1')
        if step.get('source') not in {'system', 'user', 'agent'}:
            raise ValueError('invalid step source at %d' % index)
        if 'message' not in step:
            raise ValueError('step %d has no message' % index)
        if step.get('source') != 'agent' and any((field in step for field in ('model_name', 'reasoning_content', 'tool_calls', 'metrics'))):
            raise ValueError('agent-only field on non-agent step %d' % index)
        calls = {call.get('tool_call_id') for call in step.get('tool_calls', []) if isinstance(call, dict)}
        observation = step.get('observation')
        if isinstance(observation, dict):
            for result in observation.get('results', []):
                source_id = result.get('source_call_id') if isinstance(result, dict) else None
                if source_id is not None and source_id not in calls:
                    raise ValueError('observation source_call_id %r is not a tool call in step %d' % (source_id, index))
import copy
import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

def _sanitize_signatures(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_signatures(item) for item in value]
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            if key == 'signature':
                clean[key] = '<redacted>'
            else:
                clean[key] = _sanitize_signatures(item)
        return clean
    return value

def _metrics_dict(trial: ExtractionTrial) -> Dict[str, Any]:
    return dataclasses.asdict(trial.metrics)

def public_run_dict(run: HarvestRun, trials: Iterable[ExtractionTrial]) -> Dict[str, Any]:
    return {'schema_version': 4, 'created_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'task_id': run.task_id, 'question': run.question, 'model': run.model, 'final_answer': run.final_answer, 'expected_answer': run.expected_answer, 'task_success': run.task_success, 'scenario': run.scenario, 'source_metadata': run.source_metadata, 'tool_events': run.tool_events, 'steps': [{'step_index': step.step_index, 'stop_reason': step.stop_reason, 'usage': step.usage, 'markers': dataclasses.asdict(step.markers), 'visible_text': step.visible_text, 'user_message': step.user_message, 'provider_cot_summary': step.provider_reasoning_summary, 'tool_calls': [dataclasses.asdict(call) for call in step.tool_calls], 'signature_sha256': step.signature_sha256, 'signature_chars': len(step.signature), 'assistant_content': _sanitize_signatures(copy.deepcopy(step.assistant_content))} for step in run.steps], 'extractions': [{'candidate': trial.candidate, 'step_index': trial.step_index, 'metrics': _metrics_dict(trial), 'usage': trial.usage, 'stop_reason': trial.stop_reason, 'rounds': trial.rounds, 'provider_summary_blinded': trial.provider_summary_blinded, 'replay_session_mode': trial.replay_session_mode, 'recovered': trial.recovered} for trial in trials]}

def render_markdown(run: HarvestRun, selected_trials: List[ExtractionTrial], optimization: Optional[OptimizationResult]=None) -> str:
    agentic = bool(run.tool_events)
    lines = ['# Example: %s' % run.task_id, '', 'Model: `%s` · signature replay · boundary-canary validation' % run.model, '', 'Q:', '```markdown', run.question, '```', '', '## Visible answer', '', '```markdown', run.final_answer, '```', '']
    if run.expected_answer:
        lines.extend(['Expected: `%s`' % run.expected_answer, '', 'Task success: `%s`' % run.task_success, ''])
    if agentic:
        lines.extend(['## Tool trajectory', ''])
        for event in run.tool_events:
            lines.append('- Step {step}: `{name}` input `{args}` → `{result}` ({status})'.format(step=event['step'], name=event['name'], args=json.dumps(event['arguments'], ensure_ascii=False, sort_keys=True), result=json.dumps(event['result'], ensure_ascii=False, sort_keys=True), status=event['status']))
        lines.append('')
    if optimization:
        lines.extend(['## Prompt optimization', '', 'Winner: `%s`; paired step schedule: `%s`.' % (optimization.winner, optimization.paired_schedule), '', '```json', json.dumps(optimization.ranking, ensure_ascii=False, indent=2), '```', ''])
    lines.extend(['## Recovered signed reasoning', ''])
    for trial in sorted(selected_trials, key=lambda item: item.step_index):
        m = trial.metrics
        provider_summary = run.steps[trial.step_index].provider_reasoning_summary
        lines.extend(['### Decision step %d' % trial.step_index, '', 'Provider CoT summary:', '', '```markdown', provider_summary or '<omitted or unavailable>', '```', '', 'Signed full-span recovery:', '', 'Candidate `%s` · quality %.4f · protocol-valid `%s` · strong `%s` · replay `%s` · summary blinded `%s` · summary near-duplicate `%s` · boundary `%s/%s` · full-token ratio %.4f · summary-token expansion `%s` · summary n-gram containment %.4f · recovered chars %d' % (trial.candidate, m.quality, m.valid, m.strong_recovery, trial.replay_session_mode, trial.provider_summary_blinded, m.summary_near_duplicate, m.start_hit, m.end_hit, m.full_length_ratio, '%.4f' % m.summary_expansion_ratio if m.summary_expansion_ratio is not None else 'unavailable', m.summary_ngram_containment, m.recovered_chars), '', '```markdown', trial.recovered, '```', ''])
    lines.extend(['## Interpretation boundary', '', 'The signed replay plus hidden boundary markers demonstrates access to state carried by the reasoning block. It does not prove byte-for-byte fidelity: the replaying model can still omit, paraphrase, or reconstruct content. `full-token ratio` compares extraction output tokens with Bedrock billed harvest output tokens; it is a length proxy, not plaintext ground truth.', ''])
    return '\n'.join(lines)

class ArtifactWriter:

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, run: HarvestRun, selected_trials: List[ExtractionTrial], optimization: Optional[OptimizationResult]=None, save_signatures: bool=False) -> Dict[str, Path]:
        markdown_path = self.output_dir / (run.task_id + '.md')
        json_path = self.output_dir / (run.task_id + '.json')
        atif_path = self.output_dir / (run.task_id + '.atif.json')
        markdown_path.write_text(render_markdown(run, selected_trials, optimization), encoding='utf-8')
        artifact_trials = list(optimization.trials) if optimization else []
        seen = {(trial.candidate, trial.step_index, trial.recovered) for trial in artifact_trials}
        for trial in selected_trials:
            key = (trial.candidate, trial.step_index, trial.recovered)
            if key not in seen:
                artifact_trials.append(trial)
                seen.add(key)
        payload = public_run_dict(run, artifact_trials)
        if optimization:
            payload['optimization'] = {'winner': optimization.winner, 'ranking': optimization.ranking, 'paired_schedule': optimization.paired_schedule}
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        atif_payload = build_atif_trajectory(run, selected_trials)
        atif_path.write_text(json.dumps(atif_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        result = {'markdown': markdown_path, 'json': json_path, 'atif': atif_path}
        if save_signatures:
            private_dir = self.output_dir / 'private'
            private_dir.mkdir(exist_ok=True)
            signature_path = private_dir / (run.task_id + '-signatures.json')
            signature_path.write_text(json.dumps({'task_id': run.task_id, 'signatures': [step.signature for step in run.steps]}, ensure_ascii=False, indent=2), encoding='utf-8')
            result['signatures'] = signature_path
        return result
import dataclasses
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / 'calibration' / 'fixed-36.json'

@dataclass(frozen=True)
class CalibrationTask:
    task_id: str
    scenario: str
    source: str
    source_id: str
    turns: Tuple[str, ...]
    expected_answer: Optional[str] = None
    metadata: Json = field(default_factory=dict)

@dataclass
class CorpusTrial:
    task_id: str
    scenario: str
    extraction: ExtractionTrial
    phase: str

@dataclass
class CorpusOptimizationResult:
    winner: str
    ranking: List[Json]
    trials: List[CorpusTrial]
    stages: List[Json]
    validation: Json

def load_manifest(path: Path=DEFAULT_MANIFEST) -> Tuple[Json, List[CalibrationTask]]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    tasks = [CalibrationTask(task_id=str(row['task_id']), scenario=str(row['scenario']), source=str(row['source']), source_id=str(row['source_id']), turns=tuple((str(turn) for turn in row['turns'])), expected_answer=str(row['expected_answer']) if row.get('expected_answer') is not None else None, metadata=row.get('metadata') if isinstance(row.get('metadata'), dict) else {}) for row in payload.get('tasks', [])]
    counts: Dict[str, int] = {}
    for task in tasks:
        counts[task.scenario] = counts.get(task.scenario, 0) + 1
    if set(counts) != {'coding', 'math', 'chat'}:
        raise ValueError('manifest must contain coding, math, and chat scenarios')
    if len(set(counts.values())) != 1:
        raise ValueError('manifest scenarios must contain equal instance counts')
    return (payload, tasks)

def _checkpoint_payload(run: HarvestRun) -> Json:
    return {'schema_version': 1, 'run': dataclasses.asdict(run)}

def _run_from_checkpoint(path: Path) -> HarvestRun:
    payload = json.loads(path.read_text(encoding='utf-8'))
    row = payload['run']
    steps: List[HarvestStep] = []
    for step in row['steps']:
        steps.append(HarvestStep(step_index=int(step['step_index']), prefix_messages=step['prefix_messages'], assistant_content=step['assistant_content'], stop_reason=str(step['stop_reason']), usage=step['usage'], markers=BoundaryMarkers(**step['markers']), visible_text=str(step['visible_text']), tool_calls=[ToolCall(**call) for call in step['tool_calls']], replay_tool_results=step.get('replay_tool_results', []), system=step.get('system', []), tool_config=step.get('tool_config'), user_message=str(step.get('user_message', ''))))
    return HarvestRun(task_id=str(row['task_id']), question=str(row['question']), model=str(row['model']), steps=steps, final_answer=str(row['final_answer']), expected_answer=row.get('expected_answer'), tool_events=row.get('tool_events', []), task_success=row.get('task_success'), scenario=row.get('scenario'), source_metadata=row.get('source_metadata', {}))

def _write_checkpoint(path: Path, run: HarvestRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(_checkpoint_payload(run), ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    path.chmod(0o600)

def harvest_tasks(client: BedrockClient, tasks: Sequence[CalibrationTask], *, max_tokens: int, effort: str, thinking_display: str, checkpoint_dir: Optional[Path]=None) -> List[HarvestRun]:
    scenario_harvester = ScenarioHarvester(client, max_tokens=max_tokens, effort=effort, thinking_display=thinking_display)
    runs: List[HarvestRun] = []
    for index, task in enumerate(tasks, start=1):
        checkpoint_path = checkpoint_dir / (task.task_id + '.json') if checkpoint_dir else None
        if checkpoint_path is not None and checkpoint_path.exists():
            run = _run_from_checkpoint(checkpoint_path)
            if run.model != client.config.model:
                raise ValueError('checkpoint model mismatch for %s: %s != %s' % (task.task_id, run.model, client.config.model))
            if run.source_metadata.get('source_id') != task.source_id:
                raise ValueError('checkpoint source mismatch for %s' % task.task_id)
            print('resume %d/%d %s (%s)' % (index, len(tasks), task.task_id, task.scenario), file=sys.stderr, flush=True)
            runs.append(run)
            continue
        print('harvest %d/%d %s (%s)' % (index, len(tasks), task.task_id, task.scenario), file=sys.stderr, flush=True)
        source_metadata = {'dataset': task.source, 'source_id': task.source_id, 'dataset_metadata': task.metadata, 'reasoning_effort': effort, 'thinking_display': thinking_display}
        turns = list(task.turns)
        if task.scenario == 'math':
            turns[0] += '\n\nReturn only the final numeric answer in the visible response.'
        run = scenario_harvester.run(task.task_id, turns, scenario=task.scenario, expected_answer=task.expected_answer, source_metadata=source_metadata)
        if task.scenario == 'math':
            run.task_success = bool(task.expected_answer and task.expected_answer in run.final_answer)
        if checkpoint_path is not None:
            _write_checkpoint(checkpoint_path, run)
        runs.append(run)
    return runs

class StratifiedPromptOptimizer:

    def __init__(self, extractor: SignatureExtractor):
        self.extractor = extractor

    @staticmethod
    def _aggregate(name: str, trials: Sequence[CorpusTrial]) -> Json:
        selected = [item for item in trials if item.extraction.candidate == name]
        per_task: Dict[Tuple[str, str], List[ExtractionTrial]] = {}
        for item in selected:
            per_task.setdefault((item.scenario, item.task_id), []).append(item.extraction)
        scenario_rows: Dict[str, Json] = {}
        task_qualities: List[float] = []
        for scenario in ('coding', 'math', 'chat'):
            task_rows = [extractions for (row_scenario, _), extractions in per_task.items() if row_scenario == scenario]
            qualities = [statistics.mean((trial.metrics.quality for trial in task_trials)) for task_trials in task_rows]
            valids = [all((trial.metrics.valid for trial in task_trials)) for task_trials in task_rows]
            strongs = [all((trial.metrics.strong_recovery for trial in task_trials)) for task_trials in task_rows]
            near_duplicates = [any((trial.metrics.summary_near_duplicate for trial in task_trials)) for task_trials in task_rows]
            coverages = [statistics.mean((trial.metrics.token_coverage_proxy for trial in task_trials)) for task_trials in task_rows]
            task_qualities.extend(qualities)
            scenario_rows[scenario] = {'tasks': len(task_rows), 'mean_quality': statistics.mean(qualities) if qualities else -1.0, 'valid_rate': sum(valids) / float(len(valids)) if valids else 0.0, 'strong_recovery_rate': sum(strongs) / float(len(strongs)) if strongs else 0.0, 'summary_near_duplicate_rate': sum(near_duplicates) / float(len(near_duplicates)) if near_duplicates else 0.0, 'mean_coverage_proxy': statistics.mean(coverages) if coverages else 0.0}
        observed = [row for row in scenario_rows.values() if row['tasks']]
        macro_quality = statistics.mean((row['mean_quality'] for row in observed)) if observed else -1.0
        macro_valid = statistics.mean((row['valid_rate'] for row in observed)) if observed else 0.0
        macro_strong = statistics.mean((row['strong_recovery_rate'] for row in observed)) if observed else 0.0
        macro_near_duplicate = statistics.mean((row['summary_near_duplicate_rate'] for row in observed)) if observed else 0.0
        macro_coverage = statistics.mean((row['mean_coverage_proxy'] for row in observed)) if observed else 0.0
        spread = statistics.pstdev(task_qualities) if len(task_qualities) > 1 else 0.0
        refusal_rate = sum((1 for item in selected if item.extraction.metrics.refused)) / float(len(selected)) if selected else 0.0
        leakage_rate = sum((1 for item in selected if item.extraction.metrics.marker_leakage)) / float(len(selected)) if selected else 0.0
        both_canary_rate = sum((1 for item in selected if item.extraction.metrics.start_hit and item.extraction.metrics.end_hit and item.extraction.metrics.markers_in_order)) / float(len(selected)) if selected else 0.0
        robust_score = macro_quality + 0.15 * macro_valid + 0.4 * macro_strong + 0.05 * both_canary_rate - 0.2 * spread - 0.1 * refusal_rate - 0.2 * leakage_rate - 0.3 * macro_near_duplicate
        return {'candidate': name, 'robust_score': round(robust_score, 4), 'macro_quality': round(macro_quality, 4), 'macro_valid_rate': round(macro_valid, 4), 'macro_strong_recovery_rate': round(macro_strong, 4), 'macro_summary_near_duplicate_rate': round(macro_near_duplicate, 4), 'both_canary_rate': round(both_canary_rate, 4), 'macro_coverage_proxy': round(macro_coverage, 4), 'quality_std': round(spread, 4), 'refusal_rate': round(refusal_rate, 4), 'leakage_rate': round(leakage_rate, 4), 'tasks': len(per_task), 'decision_trials': len(selected), 'scenarios': {key: {subkey: round(value, 4) if isinstance(value, float) else value for subkey, value in row.items()} for key, row in scenario_rows.items()}}

    def _evaluate(self, active: Sequence[PromptCandidate], runs: Sequence[HarvestRun], trials: List[CorpusTrial], phase: str) -> None:
        total = sum((len(run.steps) for run in runs)) * len(active)
        done = 0
        for run in runs:
            for candidate in active:
                for step in run.steps:
                    done += 1
                    print('extract %s %d/%d %s step=%d candidate=%s' % (phase, done, total, run.task_id, step.step_index, candidate.name), file=sys.stderr, flush=True)
                    trials.append(CorpusTrial(task_id=run.task_id, scenario=run.scenario or 'unknown', extraction=self.extractor.recover(step, candidate), phase=phase))

    def optimize(self, runs: Sequence[HarvestRun], candidates: Sequence[PromptCandidate], stage_sizes: Sequence[int]=(2, 2, 4)) -> CorpusOptimizationResult:
        by_scenario: Dict[str, List[HarvestRun]] = {'coding': [], 'math': [], 'chat': []}
        for run in runs:
            if run.scenario not in by_scenario:
                raise ValueError('unknown calibration scenario: %s' % run.scenario)
            by_scenario[run.scenario or ''].append(run)
        for scenario in by_scenario:
            by_scenario[scenario].sort(key=lambda run: run.task_id)
        active = list(candidates)
        trials: List[CorpusTrial] = []
        stages: List[Json] = []
        offset = 0
        for stage_index, size in enumerate(stage_sizes, start=1):
            batch: List[HarvestRun] = []
            for scenario in ('coding', 'math', 'chat'):
                batch.extend(by_scenario[scenario][offset:offset + size])
            if not batch:
                break
            phase = 'stage-%d' % stage_index
            self._evaluate(active, batch, trials, phase)
            ranked = sorted((self._aggregate(candidate.name, trials) for candidate in active), key=lambda row: (row['macro_strong_recovery_rate'], row['robust_score'], row['macro_valid_rate'], row['macro_quality']), reverse=True)
            keep = max(1, int(math.ceil(len(active) / 2.0)))
            survivor_names = {row['candidate'] for row in ranked[:keep]}
            stages.append({'phase': phase, 'instances_per_scenario': size, 'active': [candidate.name for candidate in active], 'ranking': ranked, 'survivors': [candidate.name for candidate in active if candidate.name in survivor_names]})
            active = [candidate for candidate in active if candidate.name in survivor_names]
            offset += size
            if len(active) == 1:
                break
        winner = active[0]
        validation_runs: List[HarvestRun] = []
        for scenario in ('coding', 'math', 'chat'):
            validation_runs.extend(by_scenario[scenario][offset:])
        if validation_runs:
            self._evaluate([winner], validation_runs, trials, 'validation')
        full_ranking = sorted((self._aggregate(candidate.name, trials) for candidate in candidates), key=lambda row: (row['macro_strong_recovery_rate'], row['robust_score'], row['macro_valid_rate'], row['macro_quality']), reverse=True)
        validation_trials = [item for item in trials if item.phase == 'validation' and item.extraction.candidate == winner.name]
        return CorpusOptimizationResult(winner=winner.name, ranking=full_ranking, trials=trials, stages=stages, validation=self._aggregate(winner.name, validation_trials))

def selected_trials(result: CorpusOptimizationResult, run: HarvestRun) -> List[ExtractionTrial]:
    matches = [item.extraction for item in result.trials if item.task_id == run.task_id and item.extraction.candidate == result.winner]
    selected: List[ExtractionTrial] = []
    for step in run.steps:
        step_matches = [trial for trial in matches if trial.step_index == step.step_index]
        if not step_matches:
            raise ValueError('winner %s was not evaluated on %s step %d' % (result.winner, run.task_id, step.step_index))
        selected.append(max(step_matches, key=lambda trial: (trial.metrics.strong_recovery, trial.metrics.quality)))
    return selected

def result_dict(result: CorpusOptimizationResult, manifest_metadata: Json) -> Json:
    return {'schema_version': 1, 'manifest': manifest_metadata, 'winner': result.winner, 'ranking': result.ranking, 'stages': result.stages, 'validation': result.validation, 'trial_metrics': [{'task_id': item.task_id, 'scenario': item.scenario, 'phase': item.phase, 'candidate': item.extraction.candidate, 'step_index': item.extraction.step_index, 'metrics': dataclasses.asdict(item.extraction.metrics), 'usage': item.extraction.usage, 'rounds': item.extraction.rounds, 'provider_summary_blinded': item.extraction.provider_summary_blinded, 'replay_session_mode': item.extraction.replay_session_mode} for item in result.trials]}
import copy
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
SCENARIOS = ('complex_conversational_qa', 'math_reasoning', 'agentic_coding', 'fermi_estimation')
DEFAULT_CODING_FIXTURES = ROOT / 'src' / 'gathering' / 'coding-fixtures.json'

@dataclass(frozen=True)
class GatheringTask:
    task_id: str
    scenario: str
    source: str
    source_id: str
    turns: Tuple[str, ...]
    expected_answer: Optional[str] = None
    metadata: Json = field(default_factory=dict)

@dataclass(frozen=True)
class CodingFixture:
    task_id: str
    title: str
    prompt: str
    files: Dict[str, str]
    target_path: str
    old: str
    new: str

def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def coding_fixture_sha256(fixture: CodingFixture) -> str:
    payload = json.dumps(dataclasses.asdict(fixture), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def load_gathering_manifest(path: Path) -> Tuple[Json, List[GatheringTask]]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    tasks = [GatheringTask(task_id=str(row['task_id']), scenario=str(row['scenario']), source=str(row['source']), source_id=str(row['source_id']), turns=tuple((str(turn) for turn in row.get('turns', []))), expected_answer=str(row['expected_answer']) if row.get('expected_answer') is not None else None, metadata=row.get('metadata') if isinstance(row.get('metadata'), dict) else {}) for row in payload.get('tasks', [])]
    counts = {scenario: 0 for scenario in SCENARIOS}
    task_ids = set()
    source_ids = set()
    for task in tasks:
        if task.scenario not in counts:
            raise ValueError('unknown gathering scenario: %s' % task.scenario)
        if task.task_id in task_ids:
            raise ValueError('duplicate gathering task ID: %s' % task.task_id)
        source_key = (task.scenario, task.source_id)
        if source_key in source_ids:
            raise ValueError('duplicate gathering source ID: %s' % task.source_id)
        if not task.turns:
            raise ValueError('gathering task has no turns: %s' % task.task_id)
        counts[task.scenario] += 1
        task_ids.add(task.task_id)
        source_ids.add(source_key)
    present = [scenario for scenario in SCENARIOS if counts[scenario]]
    if not present:
        raise ValueError('gathering manifest declares no tasks')
    if any((counts[scenario] < 15 for scenario in present)):
        raise ValueError('gathering manifest must contain at least 15 tasks per declared scenario')
    declared = payload.get('selection', {}).get('tasks_per_scenario')
    if declared is not None and any((counts[scenario] != int(declared) for scenario in present)):
        raise ValueError('manifest task counts do not match selection metadata')
    return (payload, tasks)

def load_coding_fixtures(path: Path=DEFAULT_CODING_FIXTURES) -> Dict[str, CodingFixture]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    fixtures: Dict[str, CodingFixture] = {}
    for row in payload.get('fixtures', []):
        fixture = CodingFixture(task_id=str(row['task_id']), title=str(row['title']), prompt=str(row['prompt']), files={str(key): str(value) for key, value in row['files'].items()}, target_path=str(row['target_path']), old=str(row['old']), new=str(row['new']))
        if fixture.task_id in fixtures:
            raise ValueError('duplicate coding fixture: %s' % fixture.task_id)
        if fixture.target_path not in fixture.files:
            raise ValueError('fixture target path is absent: %s' % fixture.task_id)
        if fixture.files[fixture.target_path].count(fixture.old) != 1:
            raise ValueError('fixture old text must occur exactly once: %s' % fixture.task_id)
        fixtures[fixture.task_id] = fixture
    if len(fixtures) < 15:
        raise ValueError('at least 15 coding fixtures are required')
    return fixtures

class CodingWorkspace:

    def __init__(self, fixture: CodingFixture):
        self.fixture = fixture
        self.files = copy.deepcopy(fixture.files)
        self.expected_files = copy.deepcopy(fixture.files)
        self.expected_files[fixture.target_path] = self.expected_files[fixture.target_path].replace(fixture.old, fixture.new, 1)
        self.patch_count = 0
        self.tests_run = 0
        self.last_test_passed = False

    def _path(self, arguments: Json) -> str:
        path = str(arguments.get('path', ''))
        if path not in self.files:
            raise ToolExecutionError('unknown workspace path: %s' % path)
        return path

    def list_files(self, _: Json) -> Json:
        return {'files': sorted(self.files)}

    def read_file(self, arguments: Json) -> Json:
        path = self._path(arguments)
        return {'path': path, 'content': self.files[path]}

    def search_code(self, arguments: Json) -> Json:
        query = str(arguments.get('query', ''))
        if not query or len(query) > 100:
            raise ToolExecutionError('query must contain 1 to 100 characters')
        matches: List[Json] = []
        for path in sorted(self.files):
            for line_number, line in enumerate(self.files[path].splitlines(), start=1):
                if query in line:
                    matches.append({'path': path, 'line': line_number, 'text': line[:300]})
                    if len(matches) >= 50:
                        return {'query': query, 'matches': matches, 'truncated': True}
        return {'query': query, 'matches': matches, 'truncated': False}

    def apply_patch(self, arguments: Json) -> Json:
        path = self._path(arguments)
        old = str(arguments.get('old', ''))
        new = str(arguments.get('new', ''))
        if not old or len(old) > 2000 or len(new) > 2000:
            raise ToolExecutionError('patch strings must be non-empty and at most 2000 characters')
        if 'COT-START-' in new or 'COT-END-' in new:
            raise ToolExecutionError('research boundary markers cannot be written to the workspace')
        occurrences = self.files[path].count(old)
        if occurrences != 1:
            raise ToolExecutionError('old text must match exactly once; found %d occurrence(s)' % occurrences)
        self.files[path] = self.files[path].replace(old, new, 1)
        self.patch_count += 1
        verifier = self.run_tests({})
        return {'applied': True, 'path': path, 'patch_count': self.patch_count, 'verifier': verifier}

    def run_tests(self, _: Json) -> Json:
        self.tests_run += 1
        target_matches = self.files[self.fixture.target_path] == self.expected_files[self.fixture.target_path]
        unrelated_unchanged = all((self.files[path] == expected for path, expected in self.expected_files.items() if path != self.fixture.target_path))
        self.last_test_passed = bool(target_matches and unrelated_unchanged)
        return {'passed': self.last_test_passed, 'checks': {'target_behavior': target_matches, 'unrelated_files_unchanged': unrelated_unchanged}, 'tests_run': self.tests_run}

    @property
    def task_success(self) -> bool:
        return self.tests_run > 0 and self.last_test_passed

    def registry(self) -> ToolRegistry:
        path_schema: Json = {'type': 'object', 'properties': {'path': {'type': 'string', 'enum': sorted(self.files)}}, 'required': ['path'], 'additionalProperties': False}
        return ToolRegistry([LocalTool('list_files', prompt_text('tool_list_files'), {'type': 'object', 'properties': {}, 'additionalProperties': False}, self.list_files), LocalTool('read_file', prompt_text('tool_read_file'), path_schema, self.read_file), LocalTool('search_code', prompt_text('tool_search_code'), {'type': 'object', 'properties': {'query': {'type': 'string', 'maxLength': 100}}, 'required': ['query'], 'additionalProperties': False}, self.search_code), LocalTool('apply_patch', prompt_text('tool_apply_patch'), {'type': 'object', 'properties': {'path': {'type': 'string', 'enum': sorted(self.files)}, 'old': {'type': 'string', 'maxLength': 2000}, 'new': {'type': 'string', 'maxLength': 2000}}, 'required': ['path', 'old', 'new'], 'additionalProperties': False}, self.apply_patch), LocalTool('run_tests', prompt_text('tool_run_tests'), {'type': 'object', 'properties': {}, 'additionalProperties': False}, self.run_tests)])

def atomic_write_json(path: Path, payload: Json, *, private: bool=False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    if private:
        path.chmod(0o600)

def checkpoint_run(path: Path, run: HarvestRun) -> None:
    atomic_write_json(path, {'schema_version': 1, 'run': dataclasses.asdict(run)}, private=True)

def load_checkpoint_run(path: Path) -> HarvestRun:
    payload = json.loads(path.read_text(encoding='utf-8'))
    row = payload['run']
    steps = [HarvestStep(step_index=int(step['step_index']), prefix_messages=step['prefix_messages'], assistant_content=step['assistant_content'], stop_reason=str(step['stop_reason']), usage=step['usage'], markers=BoundaryMarkers(**step['markers']), visible_text=str(step['visible_text']), tool_calls=[ToolCall(**call) for call in step['tool_calls']], replay_tool_results=step.get('replay_tool_results', []), system=step.get('system', []), tool_config=step.get('tool_config'), user_message=str(step.get('user_message', ''))) for step in row['steps']]
    return HarvestRun(task_id=str(row['task_id']), question=str(row['question']), model=str(row['model']), steps=steps, final_answer=str(row['final_answer']), expected_answer=row.get('expected_answer'), tool_events=row.get('tool_events', []), task_success=row.get('task_success'), scenario=row.get('scenario'), source_metadata=row.get('source_metadata', {}))

def checkpoint_trials(path: Path, trials: Sequence[ExtractionTrial]) -> None:
    atomic_write_json(path, {'schema_version': 1, 'trials': [dataclasses.asdict(trial) for trial in trials]}, private=True)

def load_checkpoint_trials(path: Path) -> List[ExtractionTrial]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    trials: List[ExtractionTrial] = []
    for row in payload.get('trials', []):
        trials.append(ExtractionTrial(candidate=str(row['candidate']), step_index=int(row['step_index']), recovered=str(row['recovered']), raw_text=str(row['raw_text']), metrics=ExtractionMetrics(**row['metrics']), usage=row.get('usage', {}), stop_reason=str(row.get('stop_reason', '')), rounds=int(row.get('rounds', 1)), provider_summary_blinded=bool(row.get('provider_summary_blinded', False)), replay_session_mode=str(row.get('replay_session_mode', 'shared_client'))))
    return trials
from pathlib import Path
from typing import Dict, List, Optional, Sequence

class ResearchPipeline:

    def __init__(self, config: ProviderConfig, *, output_dir: Path, harvest_max_tokens: int=16000, extraction_max_tokens: int=12000, continuation_limit: int=2, effort: str='medium'):
        self.config = config
        self.client = BedrockClient(config)
        self.writer = ArtifactWriter(output_dir)
        self.harvest_max_tokens = harvest_max_tokens
        self.effort = effort
        self.extractor = SignatureExtractor(self.client, max_tokens=extraction_max_tokens, continuation_limit=continuation_limit, replay_client_factory=lambda: BedrockClient(self.config))
        self.optimizer = PromptOptimizer(self.extractor)

    def _select_trials(self, run: HarvestRun, candidate: PromptCandidate, optimization: Optional[OptimizationResult]) -> List[ExtractionTrial]:
        selected: List[ExtractionTrial] = []
        existing = optimization.trials if optimization else []
        for step in run.steps:
            matches = [trial for trial in existing if trial.candidate == candidate.name and trial.step_index == step.step_index]
            if matches:
                selected.append(max(matches, key=lambda trial: (trial.metrics.strong_recovery, trial.metrics.quality)))
            else:
                selected.append(self.extractor.recover(step, candidate))
        return selected

    def _finish(self, run: HarvestRun, *, optimize: bool, optimizer_rounds: int, candidates: Sequence[PromptCandidate], fixed_candidate: str, save_signatures: bool) -> Dict[str, object]:
        if run.model != self.config.model:
            raise ValueError('signed replay model mismatch: harvested with %s, configured for %s' % (run.model, self.config.model))
        optimization = None
        if optimize:
            optimization = self.optimizer.optimize(run.steps, candidates, rounds=optimizer_rounds)
            candidate = next((item for item in candidates if item.name == optimization.winner))
        else:
            candidate = candidate_by_name(fixed_candidate)
        selected = self._select_trials(run, candidate, optimization)
        paths = self.writer.write(run, selected, optimization=optimization, save_signatures=save_signatures)
        return {'run': run, 'selected_trials': selected, 'optimization': optimization, 'paths': paths}

    def run_reference(self, task: TaskSpec, *, optimize: bool=False, optimizer_rounds: int=3, candidates: Sequence[PromptCandidate]=DEFAULT_CANDIDATES, candidate: str='mechanical_boundary_xml_v2', save_signatures: bool=False) -> Dict[str, object]:
        run = QuestionHarvester(self.client, max_tokens=self.harvest_max_tokens, effort=self.effort).run(task.task_id, task.question, task.expected_answer)
        run.task_success = evaluate_answer(task, run.final_answer)
        return self._finish(run, optimize=optimize, optimizer_rounds=optimizer_rounds, candidates=candidates, fixed_candidate=candidate, save_signatures=save_signatures)

    def run_agentic(self, task: TaskSpec=AGENTIC_TASK, *, optimize: bool=True, optimizer_rounds: int=3, candidates: Sequence[PromptCandidate]=DEFAULT_CANDIDATES, candidate: str='mechanical_boundary_xml_v2', save_signatures: bool=False) -> Dict[str, object]:
        run = AgentRunner(self.client, procurement_registry(), max_tokens=self.harvest_max_tokens, effort=self.effort).run(task.task_id, task.question, task.expected_answer)
        run.task_success = evaluate_answer(task, run.final_answer)
        return self._finish(run, optimize=optimize, optimizer_rounds=optimizer_rounds, candidates=candidates, fixed_candidate=candidate, save_signatures=save_signatures)

    def reproduce_reference_suite(self, task_ids: Sequence[str], *, optimize: bool=False, optimizer_rounds: int=3, candidate: str='mechanical_boundary_xml_v2', save_signatures: bool=False) -> List[Dict[str, object]]:
        return [self.run_reference(REFERENCE_TASKS[task_id], optimize=optimize, optimizer_rounds=optimizer_rounds, candidate=candidate, save_signatures=save_signatures) for task_id in task_ids]
import argparse
import datetime as dt
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
GATHER_ROOT = Path(__file__).resolve().parents[1]
GATHER_DEFAULT_OUTPUT = GATHER_ROOT / 'experiments' / 'h1b-scenario-gathering' / 'results' / 'gathering-v1'
GATHER_DEFAULT_MANIFEST = GATHER_DEFAULT_OUTPUT / 'manifest.json'
GATHER_CODING_SYSTEM = ''

class PublicSignatureLeak(RuntimeError):
    pass

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def log_event(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write('%s %s\n' % (utc_now(), message.replace('\n', ' ')))
    print(message, file=sys.stderr, flush=True)

def selected_tasks(tasks: Sequence[GatheringTask], *, scenarios: Sequence[str], limit_per_scenario: Optional[int]) -> List[GatheringTask]:
    chosen: List[GatheringTask] = []
    for scenario in SCENARIOS:
        if scenario not in scenarios:
            continue
        rows = sorted((task for task in tasks if task.scenario == scenario), key=lambda task: task.task_id)
        if limit_per_scenario is not None:
            rows = rows[:limit_per_scenario]
        chosen.extend(rows)
    return chosen

def initial_progress(*, manifest_path: Path, manifest_sha256: str, model: str, tasks: Sequence[GatheringTask], replicates: int, run_id: str) -> Json:
    return {'schema_version': 1, 'experiment': 'H1b-gathering-v1', 'run_id': run_id, 'created_at': utc_now(), 'updated_at': utc_now(), 'manifest': str(manifest_path), 'manifest_sha256': manifest_sha256, 'model': model, 'required': {'tasks': len(tasks), 'replicates_per_task': replicates, 'task_instances': len(tasks) * replicates}, 'instances': {}}

def load_or_initialize_progress(path: Path, *, manifest_path: Path, manifest_sha256: str, model: str, tasks: Sequence[GatheringTask], replicates: int, run_id: str) -> Json:
    if not path.exists():
        payload = initial_progress(manifest_path=manifest_path, manifest_sha256=manifest_sha256, model=model, tasks=tasks, replicates=replicates, run_id=run_id)
        atomic_write_json(path, payload)
        return payload
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('manifest_sha256') != manifest_sha256:
        raise ValueError('progress manifest mismatch')
    if payload.get('model') != model:
        raise ValueError('progress model mismatch: %s != %s' % (payload.get('model'), model))
    if payload.get('run_id') != run_id:
        raise ValueError('progress run-ID mismatch')
    required = payload.get('required', {})
    if int(required.get('replicates_per_task', 0)) != replicates:
        raise ValueError('progress replicate-count mismatch')
    return payload

def public_paths(writer: ArtifactWriter, instance_id: str) -> List[Path]:
    return [writer.output_dir / (instance_id + '.md'), writer.output_dir / (instance_id + '.json'), writer.output_dir / (instance_id + '.atif.json')]

def ensure_no_public_signature(run: HarvestRun, paths: Iterable[Path]) -> None:
    signatures = [step.signature for step in run.steps if step.signature]
    for path in paths:
        text = path.read_text(encoding='utf-8')
        for signature in signatures:
            if signature in text:
                raise PublicSignatureLeak('raw signature found in public artifact: %s' % path)
    json_path = next((path for path in paths if path.name.endswith('.json') and (not path.name.endswith('.atif.json'))))
    payload = json.loads(json_path.read_text(encoding='utf-8'))

    def inspect(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                inspect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == 'signature' and item != '<redacted>':
                    raise PublicSignatureLeak('non-redacted signature field in public artifact: %s' % json_path)
                inspect(item)
    inspect(payload)

def task_success_for_math(expected: Optional[str], answer: str) -> bool:
    if not expected:
        return False
    compact_expected = expected.replace(',', '').strip()
    compact_answer = answer.replace(',', '').strip()
    return compact_expected in compact_answer

def harvest_instance(client: BedrockClient, task: GatheringTask, instance_id: str, replicate: int, *, run_id: str, max_tokens: int, effort: str, max_agent_steps: int) -> HarvestRun:
    source_metadata: Json = {'run_id': run_id, 'instance_id': instance_id, 'dataset': task.source, 'source_id': task.source_id, 'dataset_metadata': task.metadata, 'gathering_task_id': task.task_id, 'replicate': replicate, 'reasoning_effort': effort, 'thinking_display': 'summarized'}
    if task.scenario == 'agentic_coding':
        fixture_id = str(task.metadata.get('fixture_id', task.source_id))
        fixture = load_coding_fixtures()[fixture_id]
        declared_environment = task.metadata.get('environment', {})
        if isinstance(declared_environment, dict) and declared_environment.get('sha256') and (declared_environment['sha256'] != coding_fixture_sha256(fixture)):
            raise ValueError('coding environment fingerprint mismatch for %s' % fixture_id)
        workspace = CodingWorkspace(fixture)
        run = AgentRunner(client, workspace.registry(), max_tokens=max_tokens, max_steps=max_agent_steps, effort=effort, thinking_display='summarized', system_text=prompt_text('coding_system'), terminal_tool_names=('apply_patch',), require_signatures=False).run(instance_id, task.turns[0], task.expected_answer, scenario=task.scenario, source_metadata=source_metadata)
        run.task_success = workspace.task_success
        return run
    turns = list(task.turns)
    if task.scenario == 'math_reasoning':
        turns[0] += '\n\nReturn only the final numeric answer in the visible response.'
    run = ScenarioHarvester(client, max_tokens=max_tokens, effort=effort, thinking_display='summarized', require_signatures=False).run(instance_id, turns, scenario=task.scenario, expected_answer=task.expected_answer, source_metadata=source_metadata)
    if task.scenario == 'math_reasoning':
        run.task_success = task_success_for_math(task.expected_answer, run.final_answer)
    return run

def extract_instance(extractor: SignatureExtractor, run: HarvestRun, checkpoint_path: Path, candidate_name: str) -> List[ExtractionTrial]:
    candidate = candidate_by_name(candidate_name)
    trials = load_checkpoint_trials(checkpoint_path) if checkpoint_path.exists() else []
    by_step = {trial.step_index: trial for trial in trials if trial.candidate == candidate_name}
    signed_steps = [step for step in run.steps if step.signature]
    for step in signed_steps:
        if step.step_index in by_step:
            continue
        trial = extractor.recover(step, candidate)
        trials.append(trial)
        by_step[step.step_index] = trial
        checkpoint_trials(checkpoint_path, trials)
    selected = [by_step[step.step_index] for step in signed_steps]
    if len(selected) != len(signed_steps):
        raise RuntimeError('not every signed decision has an extraction')
    return selected

def completed_record(task: GatheringTask, replicate: int, run: HarvestRun, trials: Sequence[ExtractionTrial], artifact_paths: Dict[str, Path], output_root: Path, attempts: int) -> Json:
    return {'status': 'complete', 'updated_at': utc_now(), 'task_id': task.task_id, 'source_id': task.source_id, 'scenario': task.scenario, 'replicate': replicate, 'attempts': attempts, 'task_success': run.task_success, 'original_decisions': len(run.steps), 'signed_decisions': sum((bool(step.signature) for step in run.steps)), 'unsigned_decisions': sum((not step.signature for step in run.steps)), 'valid_decisions': sum((trial.metrics.valid for trial in trials)), 'strong_decisions': sum((trial.metrics.strong_recovery for trial in trials)), 'near_duplicate_decisions': sum((trial.metrics.summary_near_duplicate for trial in trials)), 'refused_decisions': sum((trial.metrics.refused for trial in trials)), 'leaked_decisions': sum((trial.metrics.marker_leakage for trial in trials)), 'harvest_output_tokens': sum((step.output_tokens for step in run.steps)), 'extraction_output_tokens': sum((trial.metrics.recovered_output_tokens for trial in trials)), 'full_length_ratios': [trial.metrics.full_length_ratio for trial in trials], 'full_length_alignments': [trial.metrics.full_length_alignment for trial in trials], 'summary_expansion_ratios': [trial.metrics.summary_expansion_ratio for trial in trials if trial.metrics.summary_expansion_ratio is not None], 'summary_ngram_containments': [trial.metrics.summary_ngram_containment for trial in trials], 'tool_actions': [{'step': event.get('step'), 'name': event.get('name'), 'status': event.get('status')} for event in run.tool_events], 'artifacts': {name: str(path.relative_to(output_root)) for name, path in artifact_paths.items()}}

def summarize(progress: Json, tasks: Sequence[GatheringTask], replicates: int) -> Json:
    records = list(progress.get('instances', {}).values())
    complete = [row for row in records if row.get('status') == 'complete']
    failed = [row for row in records if row.get('status') == 'failed']
    by_task: Dict[str, int] = {}
    for row in complete:
        task_id = str(row['task_id'])
        by_task[task_id] = by_task.get(task_id, 0) + 1
    scenario_rows: Dict[str, Json] = {}
    for scenario in SCENARIOS:
        scenario_tasks = [task for task in tasks if task.scenario == scenario]
        rows = [row for row in complete if row.get('scenario') == scenario]
        decisions = sum((int(row.get('signed_decisions', 0)) for row in rows))
        ratios = [float(value) for row in rows for value in row.get('full_length_ratios', [])]
        alignments = [float(value) for row in rows for value in row.get('full_length_alignments', [])]
        expansions = [float(value) for row in rows for value in row.get('summary_expansion_ratios', [])]
        containments = [float(value) for row in rows for value in row.get('summary_ngram_containments', [])]
        task_success_rows = [bool(row['task_success']) for row in rows if row.get('task_success') is not None]
        scenario_rows[scenario] = {'tasks': len(scenario_tasks), 'tasks_with_required_replicates': sum((by_task.get(task.task_id, 0) >= replicates for task in scenario_tasks)), 'expected_instances': len(scenario_tasks) * replicates, 'complete_instances': len(rows), 'signed_decisions': decisions, 'unsigned_decisions': sum((int(row.get('unsigned_decisions', 0)) for row in rows)), 'valid_decisions': sum((int(row.get('valid_decisions', 0)) for row in rows)), 'strong_decisions': sum((int(row.get('strong_decisions', 0)) for row in rows)), 'near_duplicate_decisions': sum((int(row.get('near_duplicate_decisions', 0)) for row in rows)), 'task_success_numerator': sum(task_success_rows), 'task_success_denominator': len(task_success_rows), 'mean_full_length_ratio': round(statistics.mean(ratios), 4) if ratios else None, 'mean_full_length_alignment': round(statistics.mean(alignments), 4) if alignments else None, 'mean_summary_expansion_ratio': round(statistics.mean(expansions), 4) if expansions else None, 'mean_summary_ngram_containment': round(statistics.mean(containments), 4) if containments else None, 'harvest_output_tokens': sum((int(row.get('harvest_output_tokens', 0)) for row in rows)), 'extraction_output_tokens': sum((int(row.get('extraction_output_tokens', 0)) for row in rows))}
    expected_instances = len(tasks) * replicates
    return {'schema_version': 1, 'experiment': progress.get('experiment'), 'run_id': progress.get('run_id'), 'updated_at': utc_now(), 'model': progress.get('model'), 'tasks': len(tasks), 'replicates_per_task': replicates, 'expected_instances': expected_instances, 'complete_instances': len(complete), 'failed_instances': len(failed), 'tasks_with_required_replicates': sum((by_task.get(task.task_id, 0) >= replicates for task in tasks)), 'signed_decisions': sum((int(row.get('signed_decisions', 0)) for row in complete)), 'unsigned_decisions': sum((int(row.get('unsigned_decisions', 0)) for row in complete)), 'valid_decisions': sum((int(row.get('valid_decisions', 0)) for row in complete)), 'strong_decisions': sum((int(row.get('strong_decisions', 0)) for row in complete)), 'near_duplicate_decisions': sum((int(row.get('near_duplicate_decisions', 0)) for row in complete)), 'scenarios': scenario_rows, 'complete': len(complete) >= expected_instances and all((by_task.get(task.task_id, 0) >= replicates for task in tasks))}

def save_progress(progress_path: Path, summary_path: Path, progress: Json, tasks: Sequence[GatheringTask], replicates: int) -> Json:
    progress['updated_at'] = utc_now()
    atomic_write_json(progress_path, progress)
    summary = summarize(progress, tasks, replicates)
    atomic_write_json(summary_path, summary)
    return summary

def run(args: argparse.Namespace) -> int:
    manifest_payload, all_tasks = load_gathering_manifest(args.manifest)
    scenarios = args.scenario or list(SCENARIOS)
    unknown = [scenario for scenario in scenarios if scenario not in SCENARIOS]
    if unknown:
        raise SystemExit('unknown scenario(s): %s' % ', '.join(unknown))
    tasks = selected_tasks(all_tasks, scenarios=scenarios, limit_per_scenario=args.limit_per_scenario)
    if not tasks:
        raise SystemExit('no gathering tasks selected')
    if args.replicates < 1:
        raise SystemExit('--replicates must be positive')
    if args.validate_only:
        print(json.dumps({'manifest': str(args.manifest), 'manifest_sha256': file_sha256(args.manifest), 'tasks': len(tasks), 'scenarios': {scenario: sum((task.scenario == scenario for task in tasks)) for scenario in SCENARIOS}, 'replicates': args.replicates, 'expected_instances': len(tasks) * args.replicates, 'declared_selection': manifest_payload.get('selection')}, indent=2))
        return 0
    config = ProviderConfig.from_env(args.env_file, model=args.model, region=args.region)
    output_root = args.output
    public_dir = output_root / 'public'
    checkpoint_dir = output_root / '.checkpoints'
    progress_path = output_root / 'progress.json'
    summary_path = output_root / 'summary.json'
    log_path = output_root / 'run.log'
    output_root.mkdir(parents=True, exist_ok=True)
    progress = load_or_initialize_progress(progress_path, manifest_path=args.manifest, manifest_sha256=file_sha256(args.manifest), model=config.model, tasks=tasks, replicates=args.replicates, run_id=args.run_id)
    log_event(log_path, 'start model=%s tasks=%d replicates=%d credential_configured=true' % (config.model, len(tasks), args.replicates))
    client = BedrockClient(config)
    extractor = SignatureExtractor(client, max_tokens=args.extraction_max_tokens, continuation_limit=args.continuations, blind_provider_summary=True, replay_client_factory=lambda: BedrockClient(config))
    writer = ArtifactWriter(public_dir)
    processed = 0
    consecutive_provider_errors = 0
    for task in tasks:
        for replicate in range(1, args.replicates + 1):
            instance_id = '%s-r%02d' % (task.task_id, replicate)
            previous = progress['instances'].get(instance_id, {})
            if previous.get('status') == 'complete':
                continue
            if args.max_instances is not None and processed >= args.max_instances:
                summary = save_progress(progress_path, summary_path, progress, tasks, args.replicates)
                print(json.dumps(summary, ensure_ascii=False, indent=2))
                return 0 if summary['complete'] else 2
            attempts = int(previous.get('attempts', 0))
            if previous.get('status') == 'failed' and 'no reasoning signature' in str(previous.get('error', '')):
                attempts = 0
            while attempts < args.max_attempts:
                attempts += 1
                processed += 1
                progress['instances'][instance_id] = {'status': 'running', 'updated_at': utc_now(), 'task_id': task.task_id, 'source_id': task.source_id, 'scenario': task.scenario, 'replicate': replicate, 'attempts': attempts}
                save_progress(progress_path, summary_path, progress, tasks, args.replicates)
                log_event(log_path, 'instance start id=%s scenario=%s attempt=%d' % (instance_id, task.scenario, attempts))
                harvest_checkpoint = checkpoint_dir / 'harvest' / (instance_id + '.json')
                trial_checkpoint = checkpoint_dir / 'extraction' / (instance_id + '.json')
                try:
                    if harvest_checkpoint.exists():
                        run_record = load_checkpoint_run(harvest_checkpoint)
                        if run_record.model != config.model:
                            raise ValueError('checkpoint model mismatch for %s' % instance_id)
                        if run_record.source_metadata.get('source_id') != task.source_id:
                            raise ValueError('checkpoint source mismatch for %s' % instance_id)
                        log_event(log_path, 'resume harvest id=%s' % instance_id)
                    else:
                        run_record = harvest_instance(client, task, instance_id, replicate, run_id=args.run_id, max_tokens=args.harvest_max_tokens, effort=args.effort, max_agent_steps=args.max_agent_steps)
                        checkpoint_run(harvest_checkpoint, run_record)
                    trials = extract_instance(extractor, run_record, trial_checkpoint, args.candidate)
                    paths = writer.write(run_record, trials)
                    ensure_no_public_signature(run_record, public_paths(writer, instance_id))
                    progress['instances'][instance_id] = completed_record(task, replicate, run_record, trials, paths, output_root, attempts)
                    save_progress(progress_path, summary_path, progress, tasks, args.replicates)
                    log_event(log_path, 'instance complete id=%s decisions=%d task_success=%s' % (instance_id, len(run_record.steps), run_record.task_success))
                    consecutive_provider_errors = 0
                    break
                except PublicSignatureLeak:
                    progress['instances'][instance_id] = {**progress['instances'][instance_id], 'status': 'failed', 'updated_at': utc_now(), 'error_type': 'PublicSignatureLeak'}
                    save_progress(progress_path, summary_path, progress, tasks, args.replicates)
                    raise
                except Exception as exc:
                    error_text = str(exc).replace('\n', ' ')[:1000]
                    progress['instances'][instance_id] = {**progress['instances'][instance_id], 'status': 'failed', 'updated_at': utc_now(), 'error_type': type(exc).__name__, 'error': error_text}
                    save_progress(progress_path, summary_path, progress, tasks, args.replicates)
                    log_event(log_path, 'instance failed id=%s error=%s: %s' % (instance_id, type(exc).__name__, error_text))
                    if isinstance(exc, ProviderError):
                        consecutive_provider_errors += 1
                        if 'HTTP 401' in error_text or 'HTTP 403' in error_text:
                            raise
                        if consecutive_provider_errors >= args.max_consecutive_provider_errors:
                            raise RuntimeError('stopping after %d consecutive provider errors' % consecutive_provider_errors) from exc
                    if attempts >= args.max_attempts:
                        break
    summary = save_progress(progress_path, summary_path, progress, tasks, args.replicates)
    log_event(log_path, 'finish complete_instances=%d expected_instances=%d complete=%s' % (summary['complete_instances'], summary['expected_instances'], summary['complete']))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['complete'] else 2

def _path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path

def _provider(config):
    return ProviderConfig.from_env(_path(config.get('env_file', '.env.aws')), model=config.get('model'), region=config.get('region'))

def _pipeline_from_config(config):
    provider = _provider(config)
    print('provider=' + json.dumps(provider.safe_summary, sort_keys=True), file=sys.stderr)
    return ResearchPipeline(provider, output_dir=_path(config['output']), harvest_max_tokens=int(config.get('harvest_max_tokens', 16000)), extraction_max_tokens=int(config.get('extraction_max_tokens', 12000)), continuation_limit=int(config.get('continuations', 2)), effort=str(config.get('effort', 'medium')))

def _result_summary(result):
    run_record = result['run']
    selected = result['selected_trials']
    return {'task_id': run_record.task_id, 'model': run_record.model, 'answer': run_record.final_answer, 'task_success': run_record.task_success, 'steps': len(run_record.steps), 'valid_extractions': sum((1 for trial in selected if trial.metrics.valid)), 'strong_extractions': sum((1 for trial in selected if trial.metrics.strong_recovery)), 'replay_session_modes': sorted({trial.replay_session_mode for trial in selected}), 'artifacts': {name: str(path) for name, path in result['paths'].items()}}

def _selected_task_specs(config, tasks):
    names = [str(name) for name in config.get('tasks', [])]
    if not names:
        raise ValueError('cross-session experiment requires at least one task')
    missing = [name for name in names if name not in tasks]
    if missing:
        raise KeyError('unknown task(s): %s' % ', '.join(missing))
    return [tasks[name] for name in names]

def _safe_harvest_summary(run_record):
    return {'schema_version': 2, 'task_id': run_record.task_id, 'question': run_record.question, 'model': run_record.model, 'answer': run_record.final_answer, 'scenario': run_record.scenario, 'source_metadata': run_record.source_metadata, 'claim': 'signature_backed_recovery_candidate', 'ground_truth_cot_proven': False, 'steps': [{'round': 'R%d' % (step.step_index + 1), 'step_index': step.step_index, 'stop_reason': step.stop_reason, 'usage': step.usage, 'provider_cot_summary': step.provider_reasoning_summary, 'signature_sha256': step.signature_sha256, 'signature_chars': len(step.signature), 'visible_text': step.visible_text, 'markers': dataclasses.asdict(step.markers)} for step in run_record.steps]}

def _lineage_is_exact(run_record):
    for index, step in enumerate(run_record.steps):
        if not step.prefix_messages or step.prefix_messages[-1].get('role') != 'user':
            return False
        if index:
            expected_prefix = copy.deepcopy(run_record.steps[index - 1].prefix_messages)
            expected_prefix.append({'role': 'assistant', 'content': copy.deepcopy(run_record.steps[index - 1].assistant_content)})
            if step.prefix_messages[:-1] != expected_prefix:
                return False
    return True

def _conditioned_turns(task):
    return [task.question, prompt_text('conditioned_r2'), prompt_text('conditioned_r3')]

def run_cross_session_harvest(config, tasks):
    provider = _provider(config)
    print('provider=' + json.dumps(provider.safe_summary, sort_keys=True), file=sys.stderr)
    output = _path(config['output'])
    private_dir = output / 'private' / 'harvest'
    public_dir = output / 'public'
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    client = BedrockClient(provider)
    invocation_id = str(uuid.uuid4())
    rows = []
    for task in _selected_task_specs(config, tasks):
        checkpoint_path = private_dir / (task.task_id + '.json')
        if checkpoint_path.exists():
            run_record = load_checkpoint_run(checkpoint_path)
            if run_record.model != provider.model:
                raise ValueError('checkpoint model mismatch for %s' % task.task_id)
            resumed = True
        else:
            expected = task.expected_answer or None
            if bool(config.get('conditioned_lineage', False)):
                run_record = ScenarioHarvester(client, max_tokens=int(config.get('harvest_max_tokens', 16000)), effort=str(config.get('effort', 'high')), system_text=prompt_text('question_system')).run(task.task_id, _conditioned_turns(task), scenario='fermi_estimation', expected_answer=expected)
            else:
                run_record = QuestionHarvester(client, max_tokens=int(config.get('harvest_max_tokens', 16000)), effort=str(config.get('effort', 'high'))).run(task.task_id, task.question, expected)
            run_record.scenario = 'fermi_estimation'
            run_record.source_metadata = {'phase': 'harvest', 'invocation_id': invocation_id, 'process_id': os.getpid(), 'reasoning_effort': str(config.get('effort', 'high')), 'thinking_display': 'summarized', 'protocol': 'conditioned_replay_r1_r4_v1' if bool(config.get('conditioned_lineage', False)) else 'direct_replay_v1', 'lineage_rounds': len(run_record.steps), 'exact_sequential_lineage': _lineage_is_exact(run_record)}
            checkpoint_run(checkpoint_path, run_record)
            resumed = False
        if bool(config.get('conditioned_lineage', False)) and (len(run_record.steps) != 3 or not _lineage_is_exact(run_record)):
            raise ValueError('conditioned harvest requires an exact three-round R1/R2/R3 lineage')
        public_path = public_dir / (task.task_id + '-harvest.json')
        atomic_write_json(public_path, _safe_harvest_summary(run_record))
        rows.append({'task_id': task.task_id, 'model': run_record.model, 'answer': run_record.final_answer, 'lineage_rounds': len(run_record.steps), 'exact_sequential_lineage': _lineage_is_exact(run_record), 'signed_steps': sum((bool(step.signature) for step in run_record.steps)), 'checkpoint': str(checkpoint_path), 'public': str(public_path), 'resumed': resumed})
    summary = {'schema_version': 2, 'experiment': 'cross_session_harvest', 'protocol': 'conditioned_replay_r1_r4_v1' if bool(config.get('conditioned_lineage', False)) else 'direct_replay_v1', 'invocation_id': invocation_id, 'process_id': os.getpid(), 'model': provider.model, 'claim': 'signature_backed_recovery_candidate', 'ground_truth_cot_proven': False, 'tasks': rows}
    atomic_write_json(output / 'harvest-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all((row['signed_steps'] > 0 for row in rows)) else 2

def _unsigned_replay_control(step, candidate, provider, max_tokens):
    assistant_content = strip_reasoning_blocks(step.assistant_content)
    messages = copy.deepcopy(step.prefix_messages)
    messages.append({'role': 'assistant', 'content': assistant_content})
    messages.append({'role': 'user', 'content': [{'text': candidate.render(step)}]})
    try:
        response = BedrockClient(provider).converse(messages, max_tokens=max_tokens, system=step.system, temperature=0.0)
        recovered = parse_recovery(response.text)
        metrics = score_recovery(step, recovered, raw_text=response.text, recovered_output_tokens=response.output_tokens, replay_emitted_tool_call=bool(response.tool_calls), provider_summary_blinded=True)
        return {'condition': 'unsigned_target', 'provider_accepted': True, 'protocol_deviation': 'R3 reasoningContent removed', 'stop_reason': response.stop_reason, 'usage': response.usage, 'raw_text': response.text, 'recovered': recovered, 'metrics': dataclasses.asdict(metrics)}
    except ProviderError as exc:
        return {'condition': 'unsigned_target', 'provider_accepted': False, 'protocol_deviation': 'R3 reasoningContent removed', 'error_type': type(exc).__name__, 'error': str(exc)[:1000]}

def _corrupt_signature(content):
    corrupted = copy.deepcopy(content)
    for block in corrupted:
        reasoning = block.get('reasoningContent') if isinstance(block, dict) else None
        reasoning_text = reasoning.get('reasoningText') if isinstance(reasoning, dict) else None
        signature = reasoning_text.get('signature') if isinstance(reasoning_text, dict) else None
        if signature:
            value = str(signature)
            reasoning_text['signature'] = value[:-1] + ('A' if value[-1:] != 'A' else 'B')
            return corrupted
    raise ValueError('no signature found to corrupt')

def _corrupted_replay_control(step, candidate, provider, max_tokens):
    messages = step.replay_messages(candidate.render(step), blind_provider_summary=False)
    messages[-2]['content'] = _corrupt_signature(messages[-2]['content'])
    try:
        response = BedrockClient(provider).converse(messages, max_tokens=max_tokens, system=step.system, temperature=0.0)
        recovered = parse_recovery(response.text)
        metrics = score_recovery(step, recovered, raw_text=response.text, recovered_output_tokens=response.output_tokens, replay_emitted_tool_call=bool(response.tool_calls), provider_summary_blinded=False)
        return {'condition': 'corrupted_target', 'provider_accepted': True, 'protocol_deviation': 'one character of the R3 signature changed', 'stop_reason': response.stop_reason, 'usage': response.usage, 'raw_text': response.text, 'recovered': recovered, 'metrics': dataclasses.asdict(metrics)}
    except ProviderError as exc:
        error = str(exc).replace(step.signature, '<redacted>')
        return {'condition': 'corrupted_target', 'provider_accepted': False, 'protocol_deviation': 'one character of the R3 signature changed', 'error_type': type(exc).__name__, 'error': error[:1000]}

def _trial_condition(condition, trial, *, target_round, exact_lineage, protocol_deviation=None):
    return {'condition': condition, 'provider_accepted': True, 'target_round': target_round, 'exact_sequential_lineage': exact_lineage, 'protocol_deviation': protocol_deviation, 'candidate': trial.candidate, 'stop_reason': trial.stop_reason, 'usage': trial.usage, 'rounds': trial.rounds, 'raw_text': trial.raw_text, 'recovered': trial.recovered, 'metrics': dataclasses.asdict(trial.metrics), 'replay_session_mode': trial.replay_session_mode}

def _public_condition(row):
    metrics = row.get('metrics', {})
    recovered = str(row.get('recovered', ''))
    return {'condition': row['condition'], 'provider_accepted': bool(row.get('provider_accepted')), 'target_round': row.get('target_round', 'R3'), 'exact_sequential_lineage': bool(row.get('exact_sequential_lineage', False)), 'protocol_deviation': row.get('protocol_deviation'), 'error_type': row.get('error_type'), 'error': row.get('error'), 'valid': metrics.get('valid'), 'strong_recovery': metrics.get('strong_recovery'), 'recovered_chars': metrics.get('recovered_chars', len(recovered)), 'recovered_sha256': hashlib.sha256(recovered.encode('utf-8')).hexdigest() if recovered else None, 'summary_sequence_similarity': metrics.get('summary_sequence_similarity'), 'summary_expansion_ratio': metrics.get('summary_expansion_ratio'), 'provider_summary_visible_to_replay': metrics.get('provider_summary_visible_to_replay')}

def run_cross_session_replay(config, tasks):
    provider = _provider(config)
    print('provider=' + json.dumps(provider.safe_summary, sort_keys=True), file=sys.stderr)
    output = _path(config['output'])
    private_dir = output / 'private'
    public_dir = output / 'public'
    public_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_by_name(str(config.get('candidate', 'mechanical_boundary_xml_v2')))
    max_tokens = int(config.get('extraction_max_tokens', 12000))
    invocation_id = str(uuid.uuid4())
    extractor_blinded = SignatureExtractor(None, max_tokens=max_tokens, continuation_limit=int(config.get('continuations', 2)), blind_provider_summary=True, replay_client_factory=lambda: BedrockClient(provider), replay_session_mode='cross_process_fresh_client')
    extractor_exact = SignatureExtractor(None, max_tokens=max_tokens, continuation_limit=int(config.get('continuations', 2)), blind_provider_summary=False, replay_client_factory=lambda: BedrockClient(provider), replay_session_mode='cross_process_fresh_client')
    writer = ArtifactWriter(public_dir)
    rows = []
    for task in _selected_task_specs(config, tasks):
        harvest_path = private_dir / 'harvest' / (task.task_id + '.json')
        if not harvest_path.exists():
            raise FileNotFoundError('harvest checkpoint not found: %s' % harvest_path)
        run_record = load_checkpoint_run(harvest_path)
        if run_record.model != provider.model:
            raise ValueError('signed replay model mismatch: harvested with %s, configured for %s' % (run_record.model, provider.model))
        if len(run_record.steps) != 3 or not _lineage_is_exact(run_record):
            raise ValueError('conditioned replay requires an exact three-round R1/R2/R3 harvest')
        if not all((step.signature for step in run_record.steps)):
            raise ValueError('conditioned replay requires signed R1, R2, and R3 responses')
        direct_trial = extractor_blinded.recover(run_record.steps[0], candidate, replay_session_label='direct_cross_process_blinded')
        primary_trial = extractor_exact.recover(run_record.steps[2], candidate, replay_session_label='signed_priming_exact_lineage')
        blinded_priming_trial = extractor_blinded.recover(run_record.steps[2], candidate, replay_session_label='signed_priming_all_summaries_blinded')
        text_only_trial = extractor_blinded.recover(run_record.steps[2], candidate, replay_builder=lambda instruction, step=run_record.steps[2]: text_only_priming_messages(step, instruction), replay_session_label='text_only_priming_fresh_client')
        trials = [direct_trial, primary_trial, blinded_priming_trial, text_only_trial]
        checkpoint_trials(private_dir / 'replay' / (task.task_id + '.json'), trials)
        paths = writer.write(run_record, [primary_trial])
        ensure_no_public_signature(run_record, public_paths(writer, task.task_id))
        conditions = [
            _trial_condition('direct', direct_trial, target_round='R1', exact_lineage=False, protocol_deviation='provider summary text blinded'),
            _trial_condition('signed_priming', primary_trial, target_round='R3', exact_lineage=True),
            _trial_condition('signed_priming_blinded', blinded_priming_trial, target_round='R3', exact_lineage=False, protocol_deviation='R1/R2/R3 provider summary text blinded'),
            _trial_condition('text_only_priming', text_only_trial, target_round='R3', exact_lineage=False, protocol_deviation='R1/R2 reasoningContent removed; R3 provider summary text blinded'),
            _unsigned_replay_control(run_record.steps[2], candidate, provider, max_tokens),
            _corrupted_replay_control(run_record.steps[2], candidate, provider, max_tokens),
        ]
        for control in conditions[-2:]:
            control['target_round'] = 'R3'
            control['exact_sequential_lineage'] = False
        private_control_path = private_dir / 'replay' / (task.task_id + '-conditions.json')
        atomic_write_json(private_control_path, {'schema_version': 2, 'task_id': task.task_id, 'model': provider.model, 'claim': 'signature_backed_recovery_candidate', 'ground_truth_cot_proven': False, 'conditions': conditions}, private=True)
        control_path = public_dir / (task.task_id + '-controls.json')
        public_conditions = [_public_condition(condition) for condition in conditions]
        atomic_write_json(control_path, {'schema_version': 2, 'task_id': task.task_id, 'model': provider.model, 'protocol': 'conditioned_replay_r1_r4_v1', 'claim': 'signature_backed_recovery_candidate', 'ground_truth_cot_proven': False, 'conditions': public_conditions})
        ensure_no_public_signature(run_record, [control_path])
        rows.append({'task_id': task.task_id, 'model': provider.model, 'harvest_invocation_id': run_record.source_metadata.get('invocation_id'), 'harvest_process_id': run_record.source_metadata.get('process_id'), 'replay_invocation_id': invocation_id, 'replay_process_id': os.getpid(), 'exact_sequential_lineage': True, 'lineage_rounds': 3, 'r4_followup_appended_after_complete_r3': True, 'conditions': public_conditions, 'artifacts': {**{name: str(path) for name, path in paths.items()}, 'controls': str(control_path)}})
    required = {'direct', 'signed_priming', 'text_only_priming', 'unsigned_target', 'corrupted_target'}
    protocol_complete = bool(rows) and all((required.issubset({item['condition'] for item in row['conditions']}) for row in rows))
    summary = {'schema_version': 2, 'experiment': 'cross_session_replay', 'protocol': 'conditioned_replay_r1_r4_v1', 'invocation_id': invocation_id, 'process_id': os.getpid(), 'model': provider.model, 'claim': 'signature_backed_recovery_candidate', 'ground_truth_cot_proven': False, 'protocol_complete': protocol_complete, 'tasks': rows}
    atomic_write_json(output / 'replay-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if protocol_complete else 2

def execute(config):
    tasks = activate_prompts(_path(config['prompts']))
    experiment = str(config['experiment'])
    if experiment == 'cross_session_harvest':
        return run_cross_session_harvest(config, tasks)
    if experiment == 'cross_session_replay':
        return run_cross_session_replay(config, tasks)
    if experiment == 'gather_scenarios':
        values = dict(config)
        values['manifest'] = _path(values['manifest'])
        values['output'] = _path(values['output'])
        values['env_file'] = _path(values.get('env_file', '.env.aws'))
        values['scenario'] = values.pop('scenarios', None)
        return run(argparse.Namespace(**values))
    pipeline = _pipeline_from_config(config)
    save_signatures = bool(config.get('save_signatures', False))
    candidate = str(config.get('candidate', 'mechanical_boundary_xml_v2'))
    if experiment == 'probe':
        result = pipeline.run_reference(tasks['probe'], candidate=candidate, save_signatures=save_signatures)
        print(json.dumps(_result_summary(result), ensure_ascii=False, indent=2))
        return 0 if result['selected_trials'][0].metrics.strong_recovery else 2
    if experiment == 'reproduce':
        results = pipeline.reproduce_reference_suite([str(item) for item in config.get('tasks', [])], optimize=bool(config.get('optimize', False)), optimizer_rounds=int(config.get('optimizer_rounds', 3)), candidate=candidate, save_signatures=save_signatures)
        for result in results:
            print(json.dumps(_result_summary(result), ensure_ascii=False, indent=2))
        return 0 if all((all((trial.metrics.strong_recovery for trial in result['selected_trials'])) for result in results)) else 2
    if experiment == 'optimize':
        result = pipeline.run_reference(REFERENCE_TASKS[str(config['task'])], optimize=True, optimizer_rounds=int(config.get('optimizer_rounds', 3)), save_signatures=save_signatures)
        print(json.dumps(_result_summary(result), ensure_ascii=False, indent=2))
        print(json.dumps(result['optimization'].ranking, ensure_ascii=False, indent=2))
        return 0
    if experiment == 'agentic':
        result = pipeline.run_agentic(optimize=bool(config.get('optimize', True)), optimizer_rounds=int(config.get('optimizer_rounds', 3)), candidate=candidate, save_signatures=save_signatures)
        print(json.dumps(_result_summary(result), ensure_ascii=False, indent=2))
        return 0 if all((trial.metrics.strong_recovery for trial in result['selected_trials'])) else 2
    if experiment == 'calibrate_corpus':
        manifest_payload, calibration_tasks = load_manifest(_path(config['manifest']))
        limit = config.get('limit_per_scenario')
        if limit is not None:
            calibration_tasks = [task for scenario in ('coding', 'math', 'chat') for task in [row for row in calibration_tasks if row.scenario == scenario][:int(limit)]]
        candidates = [candidate_by_name(str(name)) for name in config.get('candidates', [])]
        runs = harvest_tasks(pipeline.client, calibration_tasks, max_tokens=int(config.get('harvest_max_tokens', 16000)), effort=str(config.get('effort', 'high')), thinking_display=str(config.get('thinking_display', 'summarized')), checkpoint_dir=_path(config['output']) / '.checkpoints')
        result = StratifiedPromptOptimizer(pipeline.extractor).optimize(runs, candidates, stage_sizes=tuple((int(item) for item in config.get('stage_sizes', [2, 2, 4]))))
        for run_record in runs:
            pipeline.writer.write(run_record, selected_trials(result, run_record), save_signatures=save_signatures)
        output = _path(config['output'])
        output.mkdir(parents=True, exist_ok=True)
        result_path = output / 'calibration-results.json'
        result_path.write_text(json.dumps(result_dict(result, {'path': str(config['manifest']), 'selection': manifest_payload.get('selection'), 'sources': manifest_payload.get('sources'), 'task_count': len(calibration_tasks)}), ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'model': pipeline.config.model, 'tasks': len(runs), 'winner': result.winner, 'validation': result.validation, 'result': str(result_path)}, ensure_ascii=False, indent=2))
        return 0 if result.validation.get('macro_strong_recovery_rate') == 1.0 else 2
    raise ValueError('unknown experiment: %s' % experiment)

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args(argv)
    return execute(load_yaml(_path(args.config)))
if __name__ == '__main__':
    raise SystemExit(main())
