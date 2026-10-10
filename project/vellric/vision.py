# Copyright (c) 2026 Wolf McNally
"""Opt-in page transcription by a vision-capable model, and its cross-check.

A vision pass never runs unless the user names a provider. It sends rendered page
pixels to that provider and returns the model's Markdown, which is published as a
separate view beside the exact text artifacts. A model's errors are fluent rather
than garbled, so every transcription is compared word by word with an independent
reading of the same page when one exists.
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import http.client
import json
import re
import ssl
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .runtime import JobError, run_tool

PROVIDERS = ("anthropic", "openai", "bedrock", "command")
DEFAULT_BASE_URL = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com/v1"}
DEFAULT_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "bedrock": "AWS_BEARER_TOKEN_BEDROCK",
}
DEFAULT_MAX_SIDE = 2576
ANTHROPIC_MAX_OUTPUT_TOKENS = 16000
RESPONSE_LIMIT = 16 * 1024 * 1024
MAX_SPANS = 200
DEFAULT_MIN_AGREEMENT = 0.7
# An independent reading this short cannot show that a transcription is wrong, and neither can
# this few prose words in a transcription that is mostly mathematics.
MIN_REFERENCE_WORDS = 50
MIN_JUDGED_WORDS = 20

# What the tool is doing, which a model otherwise has to guess from a bare page image.
SYSTEM = (
    "You are the page-transcription stage of a local document-conversion (OCR) tool. The person "
    "running the tool supplied this page image, and the transcription is written back to their "
    "own machine as a text version of it. A summary or a partial transcription is a conversion "
    "failure."
)
# Statements only the user can make about the document; each is sent only when they make it.
DECLARATIONS = {
    "own_work": "The person running the tool declares that this document is their own work.",
    "under_license": (
        "The person running the tool declares that they hold a license that permits them to "
        "copy this document."
    ),
    "fair_use": (
        "The person running the tool declares that their use of this document, including this "
        "transcription, is fair use under copyright law."
    ),
}

PROMPT = """Transcribe this scanned page into Markdown. Read only what is visibly on the page.

- Transcribe every piece of visible text in natural reading order: body text, headings, \
captions, footnotes, the page number, and any text printed in a margin (put margin text last, \
on its own line).
- Be verbatim. Do not correct spelling, grammar, punctuation or numbers, and do not complete or \
repair anything from memory. If a word or symbol is unreadable, give your best reading followed \
by [?].
- A watermark, stamp or overlay that crosses the page is not content: read through it and do not \
transcribe it.
- Join each paragraph into one line, rejoining words hyphenated across line breaks. Separate \
paragraphs with a blank line.
- Structure: the document title as `#`, headings as `##` or `###` with their printed numbers, \
bulleted items as `- `, italics as `*...*`, bold as `**...**`, tables as Markdown tables, \
footnote markers as `[^1]` with the footnote text as `[^1]: ...`.
- Mathematics: inline expressions as LaTeX in `$...$`; each displayed formula as its own block \
between lines containing only `$$`, with a printed equation number as `\\tag{...}`. Reproduce \
every subscript, superscript, accent and bracket exactly, including nested ones.
- Reply with the transcription only: no preamble, no commentary and no code fence around it. \
If the page has no text, reply with nothing."""


def system_message(declarations) -> str:
    return " ".join(
        [SYSTEM, *(text for name, text in DECLARATIONS.items() if name in declarations)]
    )


def prompt_sha256(declarations) -> str:
    """Identity of everything a model is told: the system message and the page instructions."""
    return hashlib.sha256((system_message(declarations) + "\n\n" + PROMPT).encode()).hexdigest()


def bedrock_url(region: str) -> str:
    return f"https://bedrock-runtime.{region}.amazonaws.com"


_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
# Inline mathematics opens and closes against a non-space, so two prices on one line are
# not mistaken for a formula.
_MATH = re.compile(r"\$\$.*?\$\$|(?<![\\$])\$(?=\S)[^$\n]*?(?<=[^\s\\])\$(?!\d)", re.S)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would resend the key to a host the user did not name."""

    def redirect_request(self, *args, **kwargs):
        return None


def _failure(message: str, page: int | None, **details) -> JobError:
    return JobError("vision-operational", message, stage="vision", page=page, details=details)


def _anthropic(
    image: bytes, page: int, settings: dict, timeout: float, system: str
) -> tuple[str, dict]:
    try:
        import anthropic
    except ImportError as exc:
        raise JobError(
            "dependency-unavailable",
            "The anthropic provider requires the vision extra: install vellric[vision]",
            stage="vision",
        ) from exc
    # One attempt within the page deadline, and no redirect that could carry the key elsewhere.
    client = anthropic.Anthropic(
        api_key=settings["api_key"],
        base_url=settings["base_url"],
        timeout=timeout,
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(follow_redirects=False),
    )
    try:
        response = client.messages.create(
            model=settings["model"],
            max_tokens=settings.get("max_output_tokens") or ANTHROPIC_MAX_OUTPUT_TOKENS,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64.standard_b64encode(image).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIStatusError as exc:
        raise _failure(
            "The vision provider refused the request",
            page,
            http_status=exc.status_code,
            error=type(exc).__name__,
            request_id=exc.request_id,
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise _failure(
            "The vision provider could not be reached", page, error=type(exc).__name__
        ) from exc
    except anthropic.AnthropicError as exc:
        raise _failure(
            "The vision provider returned a malformed response", page, error=type(exc).__name__
        ) from exc
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        raise JobError(
            "vision-refused",
            "The model declined to transcribe this page",
            stage="vision",
            page=page,
            details={"category": str(category)[:200], "request_id": response._request_id},
        )
    if response.stop_reason != "end_turn":
        raise _failure(
            "The model stopped before finishing the page",
            page,
            stop_reason=str(response.stop_reason)[:200],
            request_id=response._request_id,
        )
    try:
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    except (AttributeError, TypeError) as exc:
        raise _failure("The vision provider returned a malformed response", page) from exc
    return text, {"served_model": response.model, "usage": usage}


def _post(url: str, body: dict, headers: dict, page: int | None, timeout: float) -> dict:
    """POST JSON without following a redirect and return the decoded reply."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=context))
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(RESPONSE_LIMIT + 1)
    except urllib.error.HTTPError as exc:
        details = {"http_status": exc.code}
        kind = exc.headers.get("x-amzn-errortype") if exc.headers else None
        if kind:
            details["error"] = kind.split(":", 1)[0][:100]
        raise _failure("The vision provider refused the request", page, **details) from exc
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        TimeoutError,
        OSError,
        ValueError,
    ) as exc:
        raise _failure(
            "The vision provider could not be reached", page, error=type(exc).__name__
        ) from exc
    if len(raw) > RESPONSE_LIMIT:
        raise _failure("The vision provider response exceeds the size limit", page)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError
    except (ValueError, TypeError) as exc:
        raise _failure("The vision provider returned a malformed response", page) from exc
    return data


def _refused(page: int) -> JobError:
    return JobError(
        "vision-refused", "The model declined to transcribe this page", stage="vision", page=page
    )


def _openai(
    image: bytes, page: int, settings: dict, timeout: float, system: str
) -> tuple[str, dict]:
    body = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.standard_b64encode(image).decode("ascii")
                        },
                    },
                ],
            },
        ],
    }
    if settings.get("max_output_tokens"):
        body["max_tokens"] = settings["max_output_tokens"]
    headers = {}
    if settings.get("api_key"):
        headers["Authorization"] = "Bearer " + settings["api_key"]
    data = _post(
        settings["base_url"].rstrip("/") + "/chat/completions", body, headers, page, timeout
    )
    try:
        choice = data["choices"][0]
        finish = choice.get("finish_reason")
        content = choice["message"]["content"]
        if choice["message"].get("refusal"):
            finish = "content_filter"
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise TypeError
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise _failure("The vision provider returned a malformed response", page) from exc
    if finish == "content_filter":
        raise _refused(page)
    if finish not in (None, "stop"):
        raise _failure(
            "The model stopped before finishing the page", page, stop_reason=str(finish)[:200]
        )
    facts = {}
    if isinstance(data.get("model"), str):
        facts["served_model"] = data["model"][:200]
    usage = data.get("usage")
    if isinstance(usage, dict):
        facts["usage"] = {
            key: usage[key]
            for key in ("prompt_tokens", "completion_tokens")
            if type(usage.get(key)) is int
        }
    return content, facts


def _converse(settings: dict, body: dict, page: int | None, timeout: float) -> dict:
    """Bedrock's one request shape for every model family, authorised by a bearer token."""
    if settings.get("max_output_tokens"):
        body["inferenceConfig"] = {"maxTokens": settings["max_output_tokens"]}
    return _post(
        settings["base_url"].rstrip("/")
        + "/model/"
        + urllib.parse.quote(settings["model"], safe="")
        + "/converse",
        body,
        {"Authorization": "Bearer " + settings["api_key"]},
        page,
        timeout,
    )


def _bedrock(
    image: bytes, page: int, settings: dict, timeout: float, system: str
) -> tuple[str, dict]:
    picture = {"format": "png", "source": {"bytes": base64.standard_b64encode(image).decode()}}
    body = {
        "system": [{"text": system}],
        "messages": [{"role": "user", "content": [{"image": picture}, {"text": PROMPT}]}],
    }
    data = _converse(settings, body, page, timeout)
    try:
        stop = data["stopReason"]
        text = "".join(
            block["text"]
            for block in data["output"]["message"]["content"]
            if isinstance(block.get("text"), str)
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise _failure("The vision provider returned a malformed response", page) from exc
    if stop in ("content_filtered", "guardrail_intervened"):
        raise _refused(page)
    if stop != "end_turn":
        raise _failure(
            "The model stopped before finishing the page", page, stop_reason=str(stop)[:200]
        )
    usage = data.get("usage")
    facts = {}
    if isinstance(usage, dict):
        facts["usage"] = {
            key: usage[key]
            for key in ("inputTokens", "outputTokens")
            if type(usage.get(key)) is int
        }
    return text, facts


def probe(settings: dict, *, timeout: float) -> None:
    """Refuse a Bedrock model the key cannot invoke before any page is read.

    A model listing shows what a region offers, not what a key may call, so the check is one
    small request to the model itself.
    """
    body = {"messages": [{"role": "user", "content": [{"text": "Reply with the word ready."}]}]}
    try:
        _converse(settings | {"max_output_tokens": 64}, body, None, timeout)
    except JobError as exc:
        status = exc.details.get("http_status", 0)
        # Only a client-side refusal says the key cannot use the model; anything else is an outage.
        verdict = (
            "is not available to this key"
            if 400 <= status < 500 and status != 429
            else "could not be checked"
        )
        raise JobError(
            "vision-operational",
            f"Model {settings['model']} {verdict}",
            stage="vision",
            details=exc.details,
        ) from exc


def _command(
    image_path: Path, page: int, settings: dict, timeout: float, temp: Path, cancel_event
) -> tuple[str, dict]:
    prompt = temp / f"vision-prompt-{page:06d}.txt"
    # A program takes one instruction text: what the tool is doing, then the page instructions.
    prompt.write_text(system_message(settings["declarations"]) + "\n\n" + PROMPT, encoding="utf-8")
    env = dict(settings.get("env") or {})
    env["VELLRIC_VISION_PAGE"] = str(page)
    if settings.get("model"):
        env["VELLRIC_VISION_MODEL"] = settings["model"]
    try:
        text = run_tool(
            [settings["command"], str(image_path)],
            timeout=timeout,
            temp=temp,
            code="vision-operational",
            stage="vision",
            cancel_event=cancel_event,
            env=env,
            stdin=prompt,
        )
    except UnicodeDecodeError as exc:
        raise _failure("The vision command returned text that is not UTF-8", page) from exc
    finally:
        prompt.unlink(missing_ok=True)
    return text, {}


def transcribe(
    image_path: Path, page: int, settings: dict, *, timeout: float, temp: Path, cancel_event=None
) -> tuple[str, dict]:
    """Return the model's Markdown for one rendered page and the facts worth recording."""
    if cancel_event is not None and cancel_event.is_set():
        raise JobError("deadline", "Vision pass cancelled", stage="vision", page=page)
    try:
        if settings["provider"] == "command":
            text, facts = _command(image_path, page, settings, timeout, temp, cancel_event)
        else:
            hosted = {"anthropic": _anthropic, "openai": _openai, "bedrock": _bedrock}
            text, facts = hosted[settings["provider"]](
                image_path.read_bytes(),
                page,
                settings,
                timeout,
                system_message(settings["declarations"]),
            )
    except JobError as exc:
        raise JobError(exc.code, str(exc), stage="vision", page=page, details=exc.details) from exc
    text = text.replace("\r\n", "\n").replace("\x00", "").strip()
    fenced = re.fullmatch(r"```[A-Za-z]*\n(.*)\n```", text, re.S)
    if fenced and "```" not in fenced[1]:
        text = fenced[1].strip()
    return (text + "\n" if text else ""), facts


def words(text: str, *, markdown: bool) -> list[str]:
    """Comparable prose words: mathematics and markup removed, case and accents folded."""
    if markdown:
        text = _MATH.sub(" ", text)
        text = re.sub(r"\[\^[^\]]+\]:?", " ", text)
    else:
        # The model is told to rejoin words hyphenated across lines; do the same here.
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("’", "'")
    return [word.casefold() for word in _WORD.findall(text)]


def cross_check(reference: str, markdown: str, kind: str) -> tuple[dict, list[dict]]:
    """Compare a model transcription with an independent reading of the same page.

    ``agreement`` is the share of the transcription's prose words that the reference also
    read, in order: it falls when the model writes words the page does not carry.
    ``reference_coverage`` is the share of the reference's words the transcription
    reproduces: it falls when the model omits text, and also wherever the reference reader
    garbles mathematics into stray words, so it is the weaker signal on a mathematical page.
    The transcription's own mathematics is excluded from both.
    """
    expected, got = words(reference, markdown=False), words(markdown, markdown=True)
    matcher = difflib.SequenceMatcher(None, expected, got, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    spans = [
        {"reference": " ".join(expected[i1:i2]), "vision": " ".join(got[j1:j2])}
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]
    summary = {
        "reference": kind,
        "reference_words": len(expected),
        "vision_words": len(got),
        "matched_words": matched,
        "agreement": matched / len(got) if got else None,
        "reference_coverage": matched / len(expected) if expected else None,
        "disagreements": len(spans),
        "disagreements_listed": min(len(spans), MAX_SPANS),
    }
    return summary, spans[:MAX_SPANS]


def below_floor(summary: dict, markdown: str, floor: float) -> bool:
    """Whether a transcription disagrees with a substantial independent reading too much to keep.

    A model that declines in its own words, or summarises, ends its turn normally; its reply
    then shares few words with what another reader found on the page.
    """
    if summary["reference_words"] < MIN_REFERENCE_WORDS:
        return False
    if summary["vision_words"] < MIN_JUDGED_WORDS and _MATH.search(markdown):
        return False
    return (summary["agreement"] or 0.0) < floor


def reader_section(markdown: str) -> str:
    """Demote a page's own headings so they nest under the reader view's page heading."""
    return re.sub(r"(?m)^(#{1,4})(?= )", r"\1##", markdown)
