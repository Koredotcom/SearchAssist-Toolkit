from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse, parse_qs

from db.database import get_llm_config, get_api_key, get_base_url

logger = logging.getLogger(__name__)


def _infer_provider(model: str) -> str:
    """Infer LLM provider from model name prefix."""
    if model.startswith("claude"):
        return "anthropic"
    return "openai"


def _parse_azure_endpoint(url: str | None) -> dict | None:
    """Detect Azure OpenAI URLs and extract endpoint / api_version / deployment.

    Accepts the full chat-completions URL the Azure portal copies, e.g.:
      https://<resource>.cognitiveservices.azure.com/openai/deployments/<dep>/chat/completions?api-version=...

    Returns None for plain OpenAI / OpenAI-compatible endpoints.
    """
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    is_azure = (
        host.endswith(".cognitiveservices.azure.com")
        or host.endswith(".openai.azure.com")
        or "/openai/deployments/" in parsed.path
    )
    if not is_azure:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    deployment = None
    if len(parts) >= 3 and parts[0] == "openai" and parts[1] == "deployments":
        deployment = parts[2]
    qs = parse_qs(parsed.query)
    api_version = (qs.get("api-version") or [None])[0]
    return {
        "azure_endpoint": f"{parsed.scheme}://{host}",
        "api_version": api_version,
        "deployment": deployment,
    }


def _is_reasoning_model(name: str) -> bool:
    """Models that use max_completion_tokens (not max_tokens) and reject temperature.
    Covers o-series reasoning models AND gpt-5+ chat models."""
    n = (name or "").lower()
    return (
        n.startswith("o1") or n.startswith("o3") or n.startswith("o4")
        or n.startswith("gpt-5") or n.startswith("gpt5")
    )


def _is_o_series_model(name: str) -> bool:
    """True only for strict o-series reasoning models (o1/o3/o4).
    These reject response_format=json_object; gpt-5 chat models do NOT."""
    n = (name or "").lower()
    return n.startswith("o1") or n.startswith("o3") or n.startswith("o4")


REASONING_MIN_TOKENS = 8000
"""Floor we'll auto-raise to for reasoning models — anything lower frequently
gets consumed by internal thinking tokens before any visible content is emitted,
producing an empty response with finish_reason=length."""


def _openai_call_kwargs(model: str, max_tokens: int, temperature: float = 0.0) -> dict:
    """Return chat-completion kwargs with the right token-limit param name.

    For reasoning models (o-series, gpt-5) we also enforce a minimum budget —
    they reject explicit temperature values, AND if max_tokens is set too low
    the entire budget is spent on internal reasoning and nothing user-visible
    is returned. Auto-bumping the per-call value (not the DB) keeps things
    working even when the stored config is too tight.
    """
    if _is_reasoning_model(model):
        effective = max(max_tokens, REASONING_MIN_TOKENS) if max_tokens else REASONING_MIN_TOKENS
        if effective != max_tokens:
            logger.info(
                "Reasoning model %s — auto-raising max_tokens %d -> %d for this call "
                "(stored config is below the safe floor)",
                model, max_tokens, effective,
            )
        return {"max_completion_tokens": effective}
    return {"max_tokens": max_tokens, "temperature": temperature}


def _openai_client_and_model(app_id: str, model: str, _app_override: dict | None = None) -> tuple[Any, str]:
    """Build the right OpenAI-family client for an app.

    For Azure URLs returns (AzureOpenAI client, deployment_name).
    For everything else returns (OpenAI client, model).
    _app_override lets callers inject a temporary key/url without persisting.
    """
    if _app_override:
        key = (_app_override.get("openai_key") or "").strip()
        url = (_app_override.get("openai_base_url") or "").strip() or None
    else:
        key = get_api_key(app_id, "openai") or ""
        url = get_base_url(app_id, "openai")
    azure = _parse_azure_endpoint(url)
    if azure and azure["deployment"]:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=key,
            azure_endpoint=azure["azure_endpoint"],
            api_version=azure["api_version"] or "2024-02-01",
        )
        logger.debug(
            "OpenAI | Using Azure | endpoint=%s api_version=%s deployment=%s",
            azure["azure_endpoint"], azure["api_version"], azure["deployment"],
        )
        return client, azure["deployment"]
    from openai import OpenAI
    return OpenAI(api_key=key, base_url=url), model


class EmptyLLMResponseError(RuntimeError):
    """Raised when an LLM call succeeds at the HTTP level but the message body
    is empty / whitespace-only.

    Carries enough metadata (model, finish_reason, max_tokens) for the caller
    to surface an actionable error to the user. The most common cause for
    reasoning models (o-series, gpt-5) is that ``max_tokens`` was exhausted
    by internal thinking tokens before any visible content was emitted.
    """

    def __init__(self, *, agent_name: str, model: str, finish_reason: str | None, max_tokens: int):
        self.agent_name = agent_name
        self.model = model
        self.finish_reason = finish_reason
        self.max_tokens = max_tokens
        hint = ""
        if (finish_reason or "").lower() == "length":
            hint = (
                f" Output was truncated (finish_reason=length). "
                f"Try increasing max_tokens (currently {max_tokens})"
                + (
                    " — reasoning models often need ≥ 8000 since thinking tokens consume the budget."
                    if _is_reasoning_model(model) else "."
                )
            )
        elif (finish_reason or "").lower() == "content_filter":
            hint = " Output was blocked by the provider's content filter."
        else:
            hint = (
                f" The model returned no content"
                f"{' (finish_reason=' + finish_reason + ')' if finish_reason else ''}."
                " Check the API key, model access, and that the prompt isn't being refused."
            )
        super().__init__(
            f"{model} returned an empty response for agent '{agent_name}'.{hint}"
        )


def call_llm(app_id: str, agent_name: str, system_prompt: str, user_msg: str) -> str:
    """Call the LLM configured for *agent_name*, routing to Anthropic or OpenAI
    based on the model string stored in llm_config.

    Raises :class:`EmptyLLMResponseError` if the call succeeds but the body is
    empty / whitespace — the error carries finish_reason and a remediation hint.
    """
    cfg = get_llm_config(app_id, agent_name)
    model: str = cfg["model"]
    provider = _infer_provider(model)
    max_tokens = int(cfg.get("max_tokens") or 0)

    logger.debug(
        "[%s] Calling %s via %s | max_tokens=%s temperature=%s | prompt_chars=%d",
        agent_name, model, provider, cfg["max_tokens"], cfg["temperature"], len(user_msg),
    )

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(
                api_key=get_api_key(app_id, "anthropic"),
                base_url=get_base_url(app_id, "anthropic"),
            )
            message = client.messages.create(
                model=model,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = ""
            if message.content:
                first = message.content[0]
                raw = (getattr(first, "text", None) or "")
            text = raw.strip()
            stop_reason = getattr(message, "stop_reason", None)
            logger.debug(
                "[%s] Anthropic response received | stop_reason=%s response_chars=%d",
                agent_name, stop_reason, len(text),
            )
            if not text:
                logger.warning(
                    "[%s] Anthropic returned EMPTY content | model=%s stop_reason=%s max_tokens=%d",
                    agent_name, model, stop_reason, max_tokens,
                )
                raise EmptyLLMResponseError(
                    agent_name=agent_name, model=model,
                    finish_reason=stop_reason, max_tokens=max_tokens,
                )
            return text

        # OpenAI (gpt-*, o1*, o3*, o4*, or any other non-claude model)
        client, effective_model = _openai_client_and_model(app_id, model)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_msg})
        call_kwargs = _openai_call_kwargs(effective_model, cfg["max_tokens"], cfg["temperature"])
        # The post-bump value we actually sent, for accurate error reporting.
        effective_max = int(
            call_kwargs.get("max_completion_tokens") or call_kwargs.get("max_tokens") or max_tokens
        )
        resp = client.chat.completions.create(
            model=effective_model,
            messages=messages,
            **call_kwargs,
        )
        choice = resp.choices[0]
        raw = choice.message.content or ""  # could legitimately be None (refusal / tool_calls)
        text = raw.strip()
        finish_reason = getattr(choice, "finish_reason", None)
        logger.debug(
            "[%s] OpenAI response received | finish_reason=%s response_chars=%d",
            agent_name, finish_reason, len(text),
        )
        if not text:
            usage = getattr(resp, "usage", None)
            logger.warning(
                "[%s] OpenAI returned EMPTY content | model=%s finish_reason=%s "
                "max_tokens=%d (stored=%d) usage=%s",
                agent_name, effective_model, finish_reason, effective_max, max_tokens, usage,
            )
            raise EmptyLLMResponseError(
                agent_name=agent_name, model=effective_model,
                finish_reason=finish_reason, max_tokens=effective_max,
            )
        return text

    except EmptyLLMResponseError:
        raise
    except Exception as exc:
        logger.error(
            "[%s] LLM call FAILED | model=%s provider=%s | error: %s",
            agent_name, model, provider, exc, exc_info=True,
        )
        raise


def call_llm_json(
    app_id: str,
    agent_name: str,
    system_prompt: str,
    user_msg: str,
    max_tokens_override: int | None = None,
) -> str:
    """Like call_llm but requests JSON output.

    For OpenAI uses ``response_format={"type": "json_object"}``.
    For Anthropic the prompt already instructs JSON; response is returned as-is.
    """
    cfg = get_llm_config(app_id, agent_name)
    model: str = cfg["model"]
    max_tokens = max_tokens_override if max_tokens_override is not None else cfg["max_tokens"]
    provider = _infer_provider(model)

    logger.debug(
        "[%s/json] Calling %s via %s | max_tokens=%s | prompt_chars=%d",
        agent_name, model, provider, max_tokens, len(user_msg),
    )

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(
                api_key=get_api_key(app_id, "anthropic"),
                base_url=get_base_url(app_id, "anthropic"),
            )
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=cfg["temperature"],
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = message.content[0].text.strip()
            logger.debug("[%s/json] Anthropic JSON response | chars=%d", agent_name, len(text))
            return text

        client, effective_model = _openai_client_and_model(app_id, model)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_msg})
        extra: dict = {}
        if not _is_o_series_model(effective_model):
            extra["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(
            model=effective_model,
            messages=messages,
            **extra,
            **_openai_call_kwargs(effective_model, max_tokens, cfg["temperature"]),
        )
        text = resp.choices[0].message.content.strip()
        logger.debug("[%s/json] OpenAI JSON response | chars=%d", agent_name, len(text))
        return text

    except Exception as exc:
        logger.error(
            "[%s/json] LLM call FAILED | model=%s provider=%s | error: %s",
            agent_name, model, provider, exc, exc_info=True,
        )
        raise
