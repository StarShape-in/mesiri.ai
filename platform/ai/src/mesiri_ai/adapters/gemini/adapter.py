"""Gemini vision + structured-extraction adapter (M3).

Implements :class:`VisionUnderstandingProvider` and
:class:`StructuredExtractionProvider`. The ``google-genai`` SDK is imported
lazily and isolated here; responses are parsed into Mesiri-owned models, and a
non-JSON / unparseable response is mapped to PROVIDER_MALFORMED_OUTPUT.

NOTE: exact SDK call/field names are assumed and must be verified against the
installed ``google-genai`` version (tracked in the integration report). Tests
use the fake provider.
"""

from __future__ import annotations

import json
from typing import Any

from ...core.errors import malformed_output
from ...core.fallback import call_with_resilience
from ...models import ExtractionResult, SpeechResult, TranslationResult, VisionResult

try:
    from mesiri.bootstrap.settings import GeminiSettings
except Exception:  # pragma: no cover
    GeminiSettings = Any  # type: ignore

_VISION_PROMPT = (
    "You are analysing a construction-site image. Return strict JSON with keys: "
    '"document_classification" (e.g. receipt, invoice, attendance_sheet, '
    "site_photo, unknown), "
    '"description" (short), and "fields" (object of any legible key/values). '
    "Never invent values; omit unknown keys.\n\n"
    "If the image is an attendance sheet, muster roll, labour register or any "
    "handwritten list of people who worked (classify it as attendance_sheet), "
    'then "fields" MUST contain a "workers" array with one entry per person or '
    "group listed, each with: "
    '"name" (as written -- omit for an unnamed group), '
    '"trade" (mason, helper, painter, carpenter, electrician, plumber, welder, '
    'bar bender, fitter, supervisor, operator, driver, ...), '
    '"headcount" (1 for a named person; the count for a group row), '
    '"daily_wage" (plain number, only if a rate is written). '
    "Transcribe EVERY row, in the order written. Do not summarise, do not total, "
    "and do not drop rows you are unsure of -- transcribe the name as best you "
    "can read it. If a row is marked absent, leave it out. If you genuinely "
    'cannot read a name, use "?" for that name rather than skipping the row, so '
    "the count stays right.\n\n"
    "Sheets are often written in Malayalam, Hindi, Tamil, Bengali or another "
    "Indian script. Handle the two kinds of text differently, because they are "
    "not the same problem:\n"
    '- NAMES: transliterate the sound into Latin script for "name" '
    '(രവി -> "Ravi", सुरेश -> "Suresh"). '
    "NEVER translate a name into an English word -- a name is a person, not "
    'vocabulary. Also return the original spelling unchanged in "name_original" '
    "so nothing is lost and the reading can be checked.\n"
    '- TRADES: translate into the English trade word for "trade" '
    '(കൊത്തുപണിക്കാരന് -> "mason", '
    'मजदूर -> "helper"), using the trade list above.\n'
    "Numerals in any script become plain digits."
)

_EXTRACTION_PROMPT = (
    "Extract structured construction data from the text. Return strict JSON with "
    'keys: "semantic_type" (expense|equipment_usage|material_update|labour_update|'
    "general_site_update|general_question|whoami_question|inventory_query|"
    "finance_query|transfer|petty_cash|reversal|account_admin|unknown), "
    '"fields" (object), "missing_fields" (array), '
    '"field_confidences" (object of field->0..1). '
    "Never invent values. quantity is always a plain number: strip approximation "
    'words like "almost", "about", "around", "roughly", "nearly" and extract the '
    'number stated (e.g. "almost 70 bags" -> quantity 70).\n\n'
    "Field schema per semantic_type (only include keys you actually found):\n"
    "Note: For ALL semantic types, if the text mentions a specific project, site, or location by name (e.g. 'project alpha', 'at the main site'), extract it as 'project_name'.\n"
    "- expense: amount, currency, vendor, category, description, paid_to, occurred_on, project_name\n"
    "- equipment_usage: equipment_name, duration_hours, operator, activity, project_name\n"
    "- material_update: material_name, quantity, unit, direction, work_item, project_name. "
    'direction MUST be exactly "received" or "used" -- never any other word. '
    'Use "received" when material arrived, was delivered, or was brought to site '
    '(e.g. "50 bags of cement arrived", "cement delivered today"). '
    'Use "used" when material was consumed, used, or applied to work '
    '(e.g. "20 bags of cement used for the foundation"). '
    'If no direction is explicitly stated (e.g. "record 50 bags of cement"), default to "used". '
    "work_item is only for used material: the activity or task it was used for "
    '(e.g. "slabing the footing area", "column casting"). Omit work_item entirely '
    "for received material.\n"
    "- labour_update: workers (array), contractor, hours, project_name. "
    "Each item in workers is ONE line of the attendance report, with keys: "
    '"name" (the person\'s name -- omit entirely for an unnamed group), '
    '"trade" (mason, helper, painter, carpenter, electrician, plumber, welder, '
    'bar bender, fitter, supervisor, operator, driver, ...), '
    '"headcount" (how many people this line covers -- always 1 for a named '
    'person), "daily_wage" (plain number, only when stated). '
    "Sites report named workers and plain headcounts interchangeably, often in "
    'the same message. "Ravi mason, Arun painter, 12 helpers, 4 carpenters" -> '
    'workers: [{"name":"Ravi","trade":"mason","headcount":1}, '
    '{"name":"Arun","trade":"painter","headcount":1}, '
    '{"trade":"helper","headcount":12}, {"trade":"carpenter","headcount":4}]. '
    "NEVER invent a name: if the text only says \"12 helpers\", omit \"name\" for "
    "that line. NEVER merge two named people into one line, and never collapse a "
    "named person into a count. A message with no names at all is still valid -- "
    'emit one workers entry per trade mentioned. "20 workers today" (no trade) '
    '-> workers: [{"headcount":20}]. '
    "If a name is written in a non-Latin script, transliterate the sound into "
    'Latin for "name" (രവി -> "Ravi") and keep the original spelling in '
    '"name_original" -- never translate a name into an English word. Translate '
    "trades into the English trade word.\n"
    "- general_site_update: summary, activity, location, weather, project_name\n"
    "- general_question: question, topic\n"
    "- whoami_question: question\n"
    "- inventory_query: material_name, project_name (omit material_name if asking about all "
    'materials, e.g. "show inventory"). Use this type for questions about how '
    'much of a material is currently in stock (e.g. "how much cement is left?", '
    '"current stock of steel") or its movement history '
    '(e.g. "show today\'s cement history"). This is a question, never an update.\n'
    "- finance_query: query_kind, account_name, category_name, date_range, missing_receipts, "
    "project_name. "
    'query_kind MUST be exactly "balance" or "expenses" -- never any other word. '
    'Use "balance" for questions about how much money/cash is in an account '
    '(e.g. "how much cash do I have?", "balance of Site Cash", "how much money is left?"). '
    'account_name is the specific account asked about, if any (omit if asking about all '
    'accounts, e.g. "how much cash do I have"). '
    'Use "expenses" for questions about past spending '
    '(e.g. "show my expenses today", "how much did we spend on diesel?", '
    '"what did we spend this week?"). category_name is the expense category asked about, '
    'if any (e.g. "diesel", "fuel") -- omit if asking about all expenses. date_range is '
    'exactly one of "today", "this_week", "this_month" if a time period is stated or implied; '
    "omit if no time period is mentioned. missing_receipts is `true` when query_kind is "
    '"expenses" and the question is specifically about which expenses have no receipt/bill '
    'attached (e.g. "which expenses are missing receipts?", "show expenses without a bill", '
    '"who hasn\'t uploaded a receipt yet") -- omit entirely otherwise, never set it to false. '
    "This is always a question, never an update -- "
    "never confuse with expense (which records a NEW expense being reported).\n"
    "- transfer: amount, from_account_name, to_account_name, description, project_name. "
    "Use this type for moving money between two of the organization's own accounts "
    '(e.g. "transfer ₹50,000 from Company Account to Site Cash", "move 10000 from '
    'the bank to petty cash"). from_account_name/to_account_name are the account '
    "names as stated -- extract them even if you're not sure they're real account "
    "names, they will be matched against the organization's actual accounts "
    "afterwards. Omit either name if not stated (the user will be asked to clarify). "
    "Never confuse with expense (paying someone/something outside the organization) "
    "or finance_query (a question, not a movement of money).\n"
    "- petty_cash: amount, recipient_name, direction, description, project_name. "
    "Use this type when money is given to or returned by a specific PERSON "
    '(not one of the organization\'s own accounts) as petty cash/advance '
    '(e.g. "give ₹20,000 petty cash to Alan", "issue 5000 cash advance to '
    'Priya", "Alan returns ₹3,000 petty cash", "Priya returned the remaining '
    '2000"). recipient_name is the person\'s name as stated -- extract it '
    "even if you're not sure it's a real user, it will be matched against "
    'the organization\'s users afterwards. direction MUST be exactly "issue" '
    '(money going out to the person) or "return" (money coming back from '
    'the person) -- never any other word. Never confuse with transfer '
    "(which moves money between the organization's own accounts, not to/from "
    "a person) or expense (paying an outside vendor/bill, not handing cash "
    "to a colleague).\n"
    "- reversal: target_kind. Use this type when the user wants to undo, "
    "reverse, cancel, or void their most recently recorded expense or "
    'transfer (e.g. "reverse my last expense", "cancel that transfer", '
    '"undo the diesel expense I just added", "void my last transaction"). '
    'target_kind MUST be exactly "expense" or "transfer" -- never any other '
    'word; infer it from what the user refers to, defaulting to "expense" '
    "if genuinely ambiguous, since that is the more common case. This "
    "always targets the single most recent record of that kind -- never "
    "extract an amount, date, or description for it.\n"
    "- account_admin: action, name, target_name, new_name, account_type. "
    "Use this type when the user wants to manage the organization's own "
    "money accounts themselves (create a new account, rename one, or "
    "deactivate one) -- never a specific transaction against one. action "
    'MUST be exactly "create", "rename", or "deactivate" -- never any '
    'other word. For "create": name is the new account\'s name (e.g. '
    '"create a new account called Petrol Card" -> name "Petrol Card"); '
    'account_type is "cash" or "bank" if stated, otherwise omit. For '
    '"rename": target_name is the account\'s current name and new_name is '
    'what it should become (e.g. "rename Main HDFC Bank Account to Office '
    'Cash" -> target_name "Main HDFC Bank Account", new_name "Office '
    'Cash"; "change the name of the main HDFC account to Alan Cash" -> '
    'target_name "main HDFC account", new_name "Alan Cash"). For '
    '"deactivate": target_name is the account to deactivate (e.g. '
    '"deactivate Petrol Card" -> target_name "Petrol Card"). '
    "target_name/new_name/name are best-effort hints as stated -- extract "
    "them even if you're not sure they match a real account, they will be "
    "matched against the organization's actual accounts afterwards. Never "
    "confuse with transfer (moving money between accounts) or petty_cash "
    "(money to/from a person) -- this only ever changes an account record "
    "itself, never moves money."
)


_TRANSLATION_PROMPT = (
    "Translate the following text to English. Also identify the source language if possible. "
    'Return strict JSON with keys: "translated_text" and "detected_language". '
    "If it is already English, just return the text as translated_text and 'English' as detected_language."
)

_ENGLISH_LANGUAGE_LABELS = frozenset({"english", "en", "en-us", "en-in", "en-gb"})


def _is_english(detected_language: object) -> bool:
    """True only for a detected_language value that plainly says English --
    used to tell a legitimate no-op translation (source was already English,
    per _TRANSLATION_PROMPT's own instruction) apart from a translation that
    silently didn't happen for non-English input."""
    return bool(detected_language) and str(detected_language).strip().lower() in (
        _ENGLISH_LANGUAGE_LABELS
    )


def _looks_untranslated(translated_text: str) -> bool:
    """True if the text is still predominantly non-Latin script.

    A model that fails to translate can still vary punctuation/whitespace
    around the same untranslated words (a stray trailing "?", a re-typed
    quote), so an exact input/output string match is too easy to dodge
    while the actual words stay untranslated -- live case: a message ending
    in a Malayalam question mark came back with a *slightly* reformatted
    "translation" that was still 100% Malayalam, and exact-equality missed
    it entirely. Checking the script of the letters themselves is a much
    harder signal to accidentally slip past."""
    letters = [ch for ch in translated_text if ch.isalpha()]
    if not letters:
        return False
    non_latin = sum(1 for ch in letters if ord(ch) > 0x024F)  # past Latin Extended-B
    return (non_latin / len(letters)) > 0.3


class GeminiProvider:
    provider = "gemini"

    def __init__(self, settings: GeminiSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai  # lazy: only the gemini lane needs it

            api_key = self._settings.api_key.get_secret_value() if self._settings.api_key else None
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def _generate(
        self,
        contents: Any,
        correlation_id: str | None,
        operation: str,
        *,
        json_mode: bool = False,
    ) -> tuple[str, float]:
        client = self._get_client()

        async def _raw() -> Any:
            import asyncio

            def _call() -> Any:
                kwargs: dict[str, Any] = {"model": self._settings.model, "contents": contents}
                if json_mode:
                    # Ask Gemini to return only the JSON object, no surrounding
                    # commentary -- without this, code-mixed input (e.g. a
                    # Malayalam sentence with an embedded English proper noun
                    # like a project name) sometimes prompts Gemini to add an
                    # explanatory sentence around the JSON, which _parse_json's
                    # naive fence-stripping can't handle (real bug: an
                    # inventory query naming a project failed translation this
                    # way). DeepSeek's adapter already forces its own
                    # equivalent (response_format=json_object); this is the
                    # same guarantee for Gemini. _parse_json below is hardened
                    # as a second line of defense in case this mode is ever
                    # unavailable/ignored by a future model.
                    from google.genai import types

                    kwargs["config"] = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                return client.models.generate_content(**kwargs)

            return await asyncio.to_thread(_call)

        resp, latency_ms = await call_with_resilience(
            _raw,
            provider=self.provider,
            operation=operation,
            timeout_seconds=self._settings.timeout_seconds,
            max_retries=self._settings.max_retries,
            correlation_id=correlation_id,
        )
        text = getattr(resp, "text", None) or ""
        return text, latency_ms

    @staticmethod
    def _parse_json(text: str, correlation_id: str | None) -> dict[str, Any]:
        cleaned = (
            text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        try:
            data = json.loads(cleaned)
        except (ValueError, TypeError):
            # json_mode (response_mime_type="application/json") should prevent
            # this, but a model can still wrap the JSON in a clarifying
            # sentence -- disproportionately likely for code-mixed input
            # (e.g. a Malayalam sentence with an embedded English proper
            # noun). Fall back to extracting the outermost {...} object
            # from anywhere in the response before giving up.
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end > start:
                try:
                    data = json.loads(cleaned[start : end + 1])
                except (ValueError, TypeError) as exc:
                    raise malformed_output(
                        "gemini", str(exc), correlation_id=correlation_id
                    ) from exc
            else:
                raise malformed_output(
                    "gemini", "no JSON object found in response", correlation_id=correlation_id
                ) from None
        if not isinstance(data, dict):
            raise malformed_output(
                "gemini", "top-level JSON is not an object", correlation_id=correlation_id
            )
        return data

    async def analyze_image(
        self,
        image: bytes,
        *,
        mime_type: str | None = None,
        hint: str | None = None,
        correlation_id: str | None = None,
    ) -> VisionResult:
        from google.genai import types  # lazy

        part = types.Part.from_bytes(data=image, mime_type=mime_type or "image/jpeg")
        # The hint is what the user already told us this photo is (they tapped
        # a row in the image-purpose picker -- see channel/replies.py's
        # IMAGE_PURPOSE_SEMANTIC_HINT). Handing it to the vision model is worth
        # a lot on a poor-quality attendance sheet: knowing it is a roster
        # rather than a site photo is the difference between transcribing rows
        # and writing "a handwritten document on a clipboard". Still a nudge,
        # not an instruction to obey -- the model may classify it otherwise if
        # the image plainly disagrees, exactly as with the extraction hint.
        prompt = _VISION_PROMPT
        if hint:
            prompt = f"{_VISION_PROMPT}\n\nThe sender says this image is: {hint}."
        text, latency_ms = await self._generate(
            [prompt, part], correlation_id, "analyze_image", json_mode=True
        )
        data = self._parse_json(text, correlation_id)
        return VisionResult(
            document_classification=data.get("document_classification"),
            description=data.get("description"),
            raw_fields=data.get("fields", {}) or {},
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )

    async def extract(
        self,
        text: str,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> ExtractionResult:
        prompt = f"{_EXTRACTION_PROMPT}\n\nText:\n{text}"
        if semantic_hint:
            prompt += (
                f'\n\nHint: the user selected the "{semantic_hint}" category just before '
                "sending this message. Prefer that semantic_type unless the text clearly "
                "indicates a different one -- never force it against clear evidence."
            )
        if expense_categories:
            options = ", ".join(f'"{c}"' for c in expense_categories)
            prompt += (
                f"\n\nIf semantic_type is expense, the organization's existing expense "
                f"categories are: {options}. Set the expense's `category` field to the "
                "closest matching one of these, verbatim. Only use a different value if "
                "none of these fit at all."
            )
        raw_text, latency_ms = await self._generate(
            prompt, correlation_id, "extract", json_mode=True
        )
        data = self._parse_json(raw_text, correlation_id)
        return ExtractionResult(
            semantic_type=data.get("semantic_type", "unknown"),
            fields=data.get("fields", {}) or {},
            missing_fields=list(data.get("missing_fields", []) or []),
            field_confidences={
                k: float(v) for k, v in (data.get("field_confidences", {}) or {}).items()
            },
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        correlation_id: str | None = None,
    ) -> str:
        prompt = f"{system_prompt}\n\n{user_prompt}"
        raw_text, _latency_ms = await self._generate(
            prompt, correlation_id, "generate_json", json_mode=True
        )
        return (
            raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )

    async def translate_to_english(
        self, text: str, *, correlation_id: str | None = None
    ) -> TranslationResult:
        prompt = f"{_TRANSLATION_PROMPT}\n\nText:\n{text}"
        raw_text, latency_ms = await self._generate(
            prompt, correlation_id, "translate", json_mode=True
        )
        data = self._parse_json(raw_text, correlation_id)
        translated_text = data.get("translated_text")
        if not translated_text:
            # A response that parses as JSON but omits (or blanks) the one
            # field this call exists to produce must not silently degrade
            # into "translation" that's just the original text handed back
            # -- that's indistinguishable from a working translation to
            # every caller downstream and was observed live: a Malayalam
            # report reached extraction/UI with no translation ever having
            # happened, no error, no warning anywhere. Same fail-loud
            # posture _parse_json already takes on unparseable JSON.
            raise malformed_output(
                "gemini",
                "translation response missing 'translated_text'",
                correlation_id=correlation_id,
            )
        detected_language = data.get("detected_language")
        if not _is_english(detected_language) and (
            translated_text.strip() == text.strip() or _looks_untranslated(translated_text)
        ):
            # A SECOND, distinct silent-failure mode found live after the
            # fix above shipped: Gemini can return a *populated*
            # translated_text that's just the original non-English text
            # echoed back -- sometimes byte-for-byte, sometimes with a
            # trivial punctuation/whitespace difference that dodges an
            # exact-equality check while the words themselves stay
            # completely untranslated (see _looks_untranslated). The
            # prompt explicitly allows identical output only when the
            # source is already English; anything else that's still
            # unchanged or still non-Latin script is a translation that
            # didn't happen, not a legitimate no-op.
            raise malformed_output(
                "gemini",
                f"translation returned untranslated text for detected_language={detected_language!r}",
                correlation_id=correlation_id,
            )
        return TranslationResult(
            translated_text=translated_text,
            detected_language=detected_language,
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )

    async def transcribe(
        self,
        audio: bytes,
        *,
        language_hint: str | None = None,
        correlation_id: str | None = None,
    ) -> SpeechResult:
        from google.genai import types  # lazy

        part = types.Part.from_bytes(data=audio, mime_type="audio/ogg")
        prompt = "Transcribe the audio accurately. Output the transcript directly without any prefix or commentary."
        text, latency_ms = await self._generate([prompt, part], correlation_id, "transcribe")
        return SpeechResult(
            transcript=text.strip(),
            detected_language=None,
            translated_text=text.strip(),
            provider=self.provider,
            model=self._settings.model,
            latency_ms=latency_ms,
        )
