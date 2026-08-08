"""JSON-safe money type for API responses.

A bare `Decimal` field on a pydantic v2 response model serializes to a JSON
**string** (`"4800.00"`, not `4800.00`). Every JavaScript consumer that then
does arithmetic on it silently gets string concatenation instead of addition:

    [{total_cost: "4800.00"}, {total_cost: "3600.00"}]
        .reduce((acc, r) => acc + r.total_cost, 0)
    // "04800.003600.00", not 8400

which is exactly how a "Cumulative Labour Spend" KPI ends up rendering
`Rs 04800.003600.00`. TypeScript cannot catch it, because the value arrives
through an `any` from `res.data`, so the `number` annotation on the client is
a lie the compiler never checks.

`Money` keeps Decimal's exactness through validation and all server-side
arithmetic, and only converts at the serialization boundary so the wire value
is a real JSON number. Amounts here are `Numeric(14, 2)` -- at most 14
significant digits, comfortably inside float64's exact-integer range once
scaled -- so the conversion does not lose a paisa at these magnitudes.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

#: Same treatment for a non-money quantity that can be fractional. Man-days
#: became fractional once a muster roll's half-day mark was captured (a half
#: day is 0.5 man-days, while `headcount` stays an integer count of people),
#: and a bare Decimal would have arrived at the dashboard as a string for the
#: same reason Money documents above. Named separately so a reader can tell
#: rupees from man-days at the field.
Quantity = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
