"""DeepSeek structured-extraction adapter (M3).

Implements :class:`StructuredExtractionProvider` against DeepSeek's
OpenAI-compatible chat API (text only, no vision). Uses httpx directly so no
extra SDK is required; responses are parsed into the Mesiri-owned
``ExtractionResult`` and malformed output maps to PROVIDER_MALFORMED_OUTPUT.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ...core.errors import malformed_output
from ...core.fallback import call_with_resilience
from ...models import ExtractionResult, TranslationResult

try:
    from mesiri.bootstrap.settings import DeepSeekSettings
except Exception:  # pragma: no cover
    DeepSeekSettings = Any  # type: ignore

_ENGLISH_LANGUAGE_LABELS = frozenset({"english", "en", "en-us", "en-in", "en-gb"})


def _is_english(detected_language: object) -> bool:
    """True only for a detected_language value that plainly says English --
    used to tell a legitimate no-op translation (source was already English)
    apart from a translation that silently didn't happen for non-English
    input. Mirrors the Gemini adapter's identical helper."""
    return bool(detected_language) and str(detected_language).strip().lower() in (
        _ENGLISH_LANGUAGE_LABELS
    )


def _looks_untranslated(translated_text: str) -> bool:
    """True if the text is still predominantly non-Latin script -- a much
    harder signal to accidentally dodge than exact input/output equality
    (a model can reformat punctuation/whitespace around otherwise-untouched
    words). Mirrors the Gemini adapter's identical helper."""
    letters = [ch for ch in translated_text if ch.isalpha()]
    if not letters:
        return False
    non_latin = sum(1 for ch in letters if ord(ch) > 0x024F)  # past Latin Extended-B
    return (non_latin / len(letters)) > 0.3

_EXTRACTION_PROMPT = (
    "The message may be in any language (Malayalam, Hindi, Tamil, Bengali, "
    "English, or code-mixed) -- read it directly, do not wait for a "
    "translation. You extract structured construction-site data from a "
    "worker's message. Return STRICT JSON only, with keys: "
    '"detected_language" (the source language\'s common English name, e.g. '
    '"Malayalam", "English"), '
    '"semantic_type" (one of: expense, equipment_usage, material_update, '
    "labour_update, general_site_update, site_issue, general_question, whoami_question, "
    "inventory_query, labour_query, activity_query, dpr_request, finance_query, transfer, "
    "petty_cash, "
    "reversal, account_admin, unknown), "
    '"fields" (object of extracted values, in English except proper nouns/names), '
    '"missing_fields" (array of expected-but-absent keys), '
    '"field_confidences" (object mapping each field to 0..1). '
    "Never invent values; if unsure, omit or list under missing_fields. quantity is "
    'always a plain number: strip approximation words like "almost", "about", '
    '"around", "roughly", "nearly" and extract the number stated (e.g. "almost 70 '
    'bags" -> quantity 70).\n\n'
    "Field schema per semantic_type (only include keys you actually found):\n"
    "Note: For ALL semantic types, if the text mentions a specific project, site, or location by name (e.g. 'project alpha', 'at the main site'), extract it as 'project_name'.\n"
    "- expense: amount, currency, vendor, category, description, paid_to, occurred_on, "
    "project_name, tax_rate, tax_amount, is_tax_inclusive. tax_rate/tax_amount are only "
    "for a bill/receipt that itemizes a specific tax line (e.g. \"GST 18%\", \"CGST 9% + "
    "SGST 9%\" -- sum the parts into one tax_rate/tax_amount, \"VAT: ₹180\") -- omit both "
    "entirely if no tax is itemized, never guess or estimate a rate/amount that isn't "
    "explicitly stated. tax_rate is the plain percentage number (18, not \"18%\"); "
    "tax_amount is the plain currency amount. is_tax_inclusive is `true` when amount "
    "already includes the tax (the common case for a total-due figure) or `false` when "
    "tax is added on top of amount -- infer from context (a receipt's grand total is "
    "inclusive; a quote/invoice listing \"subtotal + tax = total\" separately means "
    "amount is the subtotal, exclusive) and omit entirely if genuinely unclear.\n"
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
    "- labour_update: workers (array), contractor, hours, project_name, occurred_on. "
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
    "If a name is spoken or written in a non-Latin script, transliterate the "
    'sound into Latin for "name" (രവി -> "Ravi") and keep the original '
    'spelling in "name_original" -- never translate a name into an English '
    "word, and never leave the name in the original script. Translate trades "
    "into the English trade word.\n"
    "- general_site_update: narrative, work_type, quantities (array), location, "
    "contractor, project_name, occurred_on, update_kind. "
    "narrative is the report in the sender's own words. work_type is the single "
    'primary kind of work if clear (e.g. "plastering", "concreting") -- omit if '
    "unclear or multiple. quantities is an array of measured amounts, each "
    '{"work_type","quantity","unit"} -- omit entirely for a narrative-only '
    'report with nothing measured. location is the free-text place on site '
    "(e.g. \"Block A\", \"2nd floor\") -- omit if unstated. contractor is the "
    'contractor/agency named, if any. update_kind is exactly one of "started", '
    '"progress", "paused", "resumed", "completed", or omitted when unclear -- '
    '"started" only for explicitly new work, "completed" only when explicitly '
    'finished, "progress" for a further update to work already underway '
    '(including a bare quantity with no other context, e.g. "180 sqm"). Never '
    "for problems/delays/blockers (those are site_issue).\n"
    "- site_issue: issue_type, severity, narrative, delay_duration_minutes, project_name, "
    'occurred_on. issue_type MUST be exactly one of "WEATHER", "MATERIAL_SHORTAGE", '
    '"LABOUR_SHORTAGE", "DRAWING_PENDING", "EQUIPMENT_BREAKDOWN", "INSPECTION_WAITING", '
    '"ACCESS", "OTHER" -- infer from context (e.g. "no cement left" -> MATERIAL_SHORTAGE, '
    '"JCB broke down" -> EQUIPMENT_BREAKDOWN, "raining since morning" -> WEATHER), '
    'defaulting to "OTHER" only when genuinely unclear. severity MUST be exactly one of '
    '"LOW", "MEDIUM", "HIGH", "CRITICAL" -- infer from the language used (e.g. "completely '
    'stopped", "urgent" -> HIGH/CRITICAL; a minor inconvenience -> LOW/MEDIUM), defaulting '
    'to "MEDIUM" when unclear. narrative is the blocker description in the sender\'s own '
    "words. delay_duration_minutes is a plain number of minutes only when stated -- omit "
    "if not stated. This type is specifically for a NEW problem/delay/blocker that stops "
    "or slows down work -- never for a plain progress report (general_site_update) and "
    'never for a QUESTION about existing issues ("any open issues?" is activity_query).\n'
    "- general_question: question, topic\n"
    "- whoami_question: question\n"
    "- inventory_query: material_name, output_format, project_name (omit material_name if "
    'asking about all materials, e.g. "show inventory"). Use this type for questions about how '
    'much of a material is currently in stock (e.g. "how much cement is left?", '
    '"current stock of steel") or its movement history '
    '(e.g. "show today\'s cement history"). This is a question, never an update. '
    'output_format is "pdf" ONLY when the user explicitly asks for the answer as a file/'
    'document (e.g. "send me the stock levels as pdf") -- omit entirely for a plain question.\n'
    "- labour_query: date_range, trade, output_format, project_name. Use this type for QUESTIONS "
    'about who worked and what labour cost (e.g. "how many workers today?", '
    '"who worked yesterday?", "labour cost this week", "how many masons on site?"). '
    "date_range is exactly one of \"today\", \"this_week\", \"this_month\" if a period "
    "is stated or implied; omit if none is. trade narrows to one trade when asked "
    '(e.g. "how many masons today" -> trade "mason"); omit for all trades. '
    'output_format is "pdf" ONLY when the user explicitly asks for the answer as a file/'
    'document (e.g. "send me the attendance list as pdf") -- omit entirely for a plain '
    "question. CRITICAL: this is a question ABOUT existing records, never a new attendance "
    'report. "14 workers today" is a labour_update (recording who worked); '
    '"how many workers today?" is a labour_query (asking). Getting this backwards '
    "would record workers instead of counting them.\n"
    "- activity_query: date_range, project_name, work_type, output_format. Use this type for "
    'QUESTIONS about progress already logged or open site issues (e.g. "what did I log today?", '
    '"what happened on site X yesterday?", "show today\'s site log", "any open issues?"). '
    'date_range is exactly one of "today", "this_week", "this_month" if a period is stated or '
    "implied; omit if none is. work_type narrows to one kind of work when asked; omit for "
    'everything. output_format is "pdf" ONLY when the user explicitly asks for the answer as a '
    'file/document (e.g. "send me today\'s site log as pdf") -- omit entirely for a plain '
    "question. CRITICAL: this is a question ABOUT existing progress/issue records, never a new "
    'report. "180 sqm plastering done" is a general_site_update (recording work); "what did I '
    'log today?" is an activity_query (asking). Getting this backwards would try to record a '
    "report instead of answering a question.\n"
    "- finance_query: query_kind, account_name, category_name, date_range, missing_receipts, "
    "output_format, project_name. "
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
    'output_format is "pdf" ONLY when the user explicitly asks for the answer as a file/'
    'document (e.g. "send me my balance as pdf", "export my expenses as pdf", "pdf of '
    'today\'s expenses", "can I get that as a document") -- omit entirely for a plain '
    "question that expects a normal chat reply. "
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


class DeepSeekExtractionProvider:
    provider = "deepseek"

    def __init__(self, settings: DeepSeekSettings) -> None:
        self._s = settings

    async def extract(
        self,
        text: str,
        *,
        semantic_hint: str | None = None,
        expense_categories: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> ExtractionResult:
        api_key = self._s.api_key.get_secret_value() if self._s.api_key else None
        system_prompt = _EXTRACTION_PROMPT
        if semantic_hint:
            system_prompt += (
                f'\n\nHint: the user selected the "{semantic_hint}" category just before '
                "sending this message. Prefer that semantic_type unless the text clearly "
                "indicates a different one -- never force it against clear evidence."
            )
        if expense_categories:
            options = ", ".join(f'"{c}"' for c in expense_categories)
            system_prompt += (
                f"\n\nIf semantic_type is expense, the organization's existing expense "
                f"categories are: {options}. Set the expense's `category` field to the "
                "closest matching one of these, verbatim. Only use a different value if "
                "none of these fit at all."
            )

        async def _raw() -> Any:
            async with httpx.AsyncClient(timeout=self._s.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._s.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._s.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0,
                    },
                )
                resp.raise_for_status()
                return resp.json()

        raw, latency_ms = await call_with_resilience(
            _raw,
            provider=self.provider,
            operation="extract",
            timeout_seconds=self._s.timeout_seconds,
            max_retries=self._s.max_retries,
            correlation_id=correlation_id,
        )
        try:
            content = raw["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise malformed_output("deepseek", str(exc), correlation_id=correlation_id) from exc

        return ExtractionResult(
            semantic_type=data.get("semantic_type", "unknown"),
            fields=data.get("fields", {}) or {},
            missing_fields=list(data.get("missing_fields", []) or []),
            field_confidences={
                k: float(v) for k, v in (data.get("field_confidences", {}) or {}).items()
            },
            detected_language=data.get("detected_language"),
            provider=self.provider,
            model=self._s.model,
            latency_ms=latency_ms,
        )

    async def translate_to_english(
        self, text: str, *, correlation_id: str | None = None
    ) -> TranslationResult:
        api_key = self._s.api_key.get_secret_value() if self._s.api_key else None
        system_prompt = (
            "Translate the following text to English. "
            "Return STRICT JSON only with keys: "
            '"translated_text" (string) and "detected_language" (ISO-639-1 code or null). '
            "Never add commentary."
        )

        async def _raw() -> Any:
            async with httpx.AsyncClient(timeout=self._s.timeout_seconds) as client:
                resp = await client.post(
                    f"{self._s.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self._s.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0,
                    },
                )
                resp.raise_for_status()
                return resp.json()

        raw, latency_ms = await call_with_resilience(
            _raw,
            provider=self.provider,
            operation="translate",
            timeout_seconds=self._s.timeout_seconds,
            max_retries=self._s.max_retries,
            correlation_id=correlation_id,
        )
        try:
            content = raw["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise malformed_output("deepseek", str(exc), correlation_id=correlation_id) from exc

        translated_text = data.get("translated_text")
        if not translated_text:
            # Same fail-loud posture as the malformed-JSON case above --
            # see the Gemini adapter's equivalent guard for why silently
            # falling back to the original text here is unacceptable (it
            # was previously indistinguishable from a working translation).
            raise malformed_output(
                "deepseek",
                "translation response missing 'translated_text'",
                correlation_id=correlation_id,
            )
        detected_language = data.get("detected_language")
        if not _is_english(detected_language) and (
            translated_text.strip() == text.strip() or _looks_untranslated(translated_text)
        ):
            # A second, distinct silent-failure mode: a *populated*
            # translated_text that's still untranslated -- sometimes
            # byte-for-byte identical, sometimes just reformatted
            # punctuation/whitespace around otherwise-untouched words
            # (see _looks_untranslated). See the Gemini adapter's
            # identical guard for the live bug this closes.
            raise malformed_output(
                "deepseek",
                f"translation returned untranslated text for detected_language={detected_language!r}",
                correlation_id=correlation_id,
            )
        return TranslationResult(
            translated_text=translated_text,
            detected_language=detected_language,
            provider=self.provider,
            model=self._s.model,
            latency_ms=latency_ms,
        )
