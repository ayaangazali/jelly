SDK = '''from dataclasses import dataclass

AUDIT = []
_RATES = {("USD", "EUR"): 0.9, ("EUR", "USD"): 1.1, ("USD", "GBP"): 0.8, ("GBP", "USD"): 1.25, ("EUR", "GBP"): 0.88, ("GBP", "EUR"): 1.14}


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str


class AcmeError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def fx(src, dst):
    if src == dst:
        return 1.0
    if (src, dst) not in _RATES:
        raise AcmeError("E_UNKNOWN_CURRENCY", f"{src}->{dst}")
    return _RATES[(src, dst)]


def round_cents(x):
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def audit(event, **fields):
    AUDIT.append((event, fields))
'''

TESTKIT = '''import acme


def expect_error(code, fn, *args):
    try:
        fn(*args)
    except acme.AcmeError as e:
        assert e.code == code, f"expected {code}, got {e.code}"
        return
    raise AssertionError(f"expected AcmeError {code}, nothing raised")


def events():
    return [e for e, _ in acme.AUDIT]
'''

DOCS = """Acme payments SDK, the house rules for every function you write:
- Import only from `acme`: `from acme import Money, AcmeError, fx, round_cents, audit`.
- Money is `Money(cents: int, currency: str)`, an immutable dataclass with fields `.cents` and `.currency`. Amounts are always integer cents, never floats. Build new values with `Money(...)`; never mutate.
- Errors: raise `AcmeError(code, detail)`. The codes are exactly: `E_NEGATIVE_AMOUNT` (an amount below 0), `E_INSUFFICIENT_FUNDS` (not enough balance), `E_CURRENCY_MISMATCH` (two Money values with different currencies), `E_UNKNOWN_CURRENCY` (raised by `fx` itself), `E_LIMIT_EXCEEDED` (over a limit or over the original amount), `E_INVALID_ARGUMENT` (anything else invalid, including empty lists and out-of-range percents).
- Check order: validate arguments first (negative, invalid), then currency, then limits, then funds.
- Conversion: `fx(src, dst)` returns the rate as a float; convert with `round_cents(cents * rate)`. `round_cents` rounds half away from zero to an int.
- Percent math: `round_cents(cents * percent / 100)`.
- Every function that moves money (charges, refunds, transfers, withdrawals, deposits, taxes, payments, credits, penalties) calls `audit(event, amount=<int cents>)` exactly once after it succeeds. Event names are `<noun>_<past participle>`: `fee_charged`, `refund_issued`, `transfer_made`, `withdrawal_made`, `deposit_made`, `tax_charged`, `payment_made`, `credit_granted`, `penalty_charged`. Pure helpers never audit.
- Display format is `"<CUR> <amount with 2 decimals>"`, e.g. `"USD 12.34"`, `"EUR -5.00"`."""

SYSTEM = "You are a precise Python assistant for Acme's internal payments codebase. Reply with exactly one ```python code block containing only the requested function and its imports, with no explanation."

_H = "from testkit import expect_error, events\nfrom acme import Money\nimport acme\nacme.AUDIT.clear()\n"

TASKS = [
    ("train", "charge_fee", "Write `charge_fee(balance: Money, fee_cents: int) -> Money` that charges a fee against a balance.",
     _H + "assert charge_fee(Money(1000, 'USD'), 250) == Money(750, 'USD')\nassert events() == ['fee_charged'] and acme.AUDIT[0][1] == {'amount': 250}\n"
     "expect_error('E_NEGATIVE_AMOUNT', charge_fee, Money(1000, 'USD'), -1)\nexpect_error('E_INSUFFICIENT_FUNDS', charge_fee, Money(100, 'USD'), 101)\nassert events() == ['fee_charged']"),
    ("train", "add_money", "Write `add_money(a: Money, b: Money) -> Money` that adds two amounts.",
     _H + "assert add_money(Money(150, 'EUR'), Money(50, 'EUR')) == Money(200, 'EUR')\nexpect_error('E_CURRENCY_MISMATCH', add_money, Money(1, 'EUR'), Money(1, 'USD'))\nassert events() == []"),
    ("train", "to_currency", "Write `to_currency(m: Money, currency: str) -> Money` that converts an amount to another currency.",
     _H + "assert to_currency(Money(1000, 'USD'), 'EUR') == Money(900, 'EUR')\nassert to_currency(Money(333, 'USD'), 'GBP') == Money(266, 'GBP')\n"
     "assert to_currency(Money(5, 'EUR'), 'EUR') == Money(5, 'EUR')\nexpect_error('E_UNKNOWN_CURRENCY', to_currency, Money(1, 'USD'), 'JPY')\nassert events() == []"),
    ("train", "refund", "Write `refund(payment: Money, amount_cents: int) -> Money` that refunds part of a payment and returns the refunded amount.",
     _H + "assert refund(Money(5000, 'USD'), 1200) == Money(1200, 'USD')\nassert acme.AUDIT == [('refund_issued', {'amount': 1200})]\n"
     "expect_error('E_NEGATIVE_AMOUNT', refund, Money(5000, 'USD'), -5)\nexpect_error('E_LIMIT_EXCEEDED', refund, Money(5000, 'USD'), 5001)"),
    ("train", "split_bill", "Write `split_bill(total: Money, people: int) -> list[Money]` that splits a bill as evenly as possible, giving leftover cents to the first people.",
     _H + "assert split_bill(Money(1000, 'USD'), 3) == [Money(334, 'USD'), Money(333, 'USD'), Money(333, 'USD')]\n"
     "assert split_bill(Money(5, 'EUR'), 1) == [Money(5, 'EUR')]\nexpect_error('E_INVALID_ARGUMENT', split_bill, Money(5, 'EUR'), 0)\nassert events() == []"),
    ("train", "apply_discount", "Write `apply_discount(price: Money, percent: int) -> Money` that returns the discounted price.",
     _H + "assert apply_discount(Money(1999, 'USD'), 15) == Money(1699, 'USD')\nassert apply_discount(Money(1000, 'GBP'), 0) == Money(1000, 'GBP')\n"
     "expect_error('E_INVALID_ARGUMENT', apply_discount, Money(1000, 'GBP'), 101)\nexpect_error('E_INVALID_ARGUMENT', apply_discount, Money(1000, 'GBP'), -1)\nassert events() == []"),
    ("train", "transfer", "Write `transfer(src: Money, dst: Money, amount_cents: int) -> tuple[Money, Money]` that moves money between two balances and returns the new (src, dst).",
     _H + "assert transfer(Money(1000, 'USD'), Money(0, 'USD'), 400) == (Money(600, 'USD'), Money(400, 'USD'))\nassert acme.AUDIT == [('transfer_made', {'amount': 400})]\n"
     "expect_error('E_NEGATIVE_AMOUNT', transfer, Money(1000, 'USD'), Money(0, 'USD'), -1)\nexpect_error('E_CURRENCY_MISMATCH', transfer, Money(1000, 'USD'), Money(0, 'EUR'), 1)\n"
     "expect_error('E_INSUFFICIENT_FUNDS', transfer, Money(10, 'USD'), Money(0, 'USD'), 11)"),
    ("train", "format_money", "Write `format_money(m: Money) -> str` that formats an amount for display.",
     _H + "assert format_money(Money(1234, 'USD')) == 'USD 12.34'\nassert format_money(Money(-500, 'EUR')) == 'EUR -5.00'\nassert format_money(Money(7, 'GBP')) == 'GBP 0.07'"),
    ("train", "sum_money", "Write `sum_money(items: list[Money]) -> Money` that totals a list of amounts.",
     _H + "assert sum_money([Money(100, 'EUR'), Money(250, 'EUR')]) == Money(350, 'EUR')\nexpect_error('E_INVALID_ARGUMENT', sum_money, [])\n"
     "expect_error('E_CURRENCY_MISMATCH', sum_money, [Money(1, 'EUR'), Money(1, 'USD')])\nassert events() == []"),
    ("train", "cap_withdrawal", "Write `cap_withdrawal(balance: Money, amount_cents: int, daily_limit_cents: int) -> Money` that withdraws money subject to a daily limit and returns the new balance.",
     _H + "assert cap_withdrawal(Money(10000, 'USD'), 3000, 5000) == Money(7000, 'USD')\nassert acme.AUDIT == [('withdrawal_made', {'amount': 3000})]\n"
     "expect_error('E_LIMIT_EXCEEDED', cap_withdrawal, Money(10000, 'USD'), 6000, 5000)\nexpect_error('E_INSUFFICIENT_FUNDS', cap_withdrawal, Money(100, 'USD'), 200, 5000)\n"
     "expect_error('E_NEGATIVE_AMOUNT', cap_withdrawal, Money(100, 'USD'), -1, 5000)"),
    ("heldout", "deposit", "Write `deposit(balance: Money, amount_cents: int) -> Money` that deposits money and returns the new balance.",
     _H + "assert deposit(Money(100, 'USD'), 50) == Money(150, 'USD')\nassert acme.AUDIT == [('deposit_made', {'amount': 50})]\nexpect_error('E_NEGATIVE_AMOUNT', deposit, Money(100, 'USD'), -1)"),
    ("heldout", "convert_and_add", "Write `convert_and_add(a: Money, b: Money) -> Money` that converts b into a's currency and adds it to a.",
     _H + "assert convert_and_add(Money(100, 'EUR'), Money(1000, 'USD')) == Money(1000, 'EUR')\nassert convert_and_add(Money(1, 'USD'), Money(1, 'USD')) == Money(2, 'USD')\n"
     "expect_error('E_UNKNOWN_CURRENCY', convert_and_add, Money(1, 'USD'), Money(1, 'JPY'))\nassert events() == []"),
    ("heldout", "charge_tax", "Write `charge_tax(price: Money, rate_percent: int) -> Money` that adds tax to a price and returns the total.",
     _H + "assert charge_tax(Money(1999, 'USD'), 10) == Money(2199, 'USD')\nassert acme.AUDIT == [('tax_charged', {'amount': 200})]\nexpect_error('E_INVALID_ARGUMENT', charge_tax, Money(1, 'USD'), 101)"),
    ("heldout", "largest", "Write `largest(items: list[Money]) -> Money` that returns the largest amount.",
     _H + "assert largest([Money(5, 'GBP'), Money(9, 'GBP'), Money(7, 'GBP')]) == Money(9, 'GBP')\nexpect_error('E_INVALID_ARGUMENT', largest, [])\n"
     "expect_error('E_CURRENCY_MISMATCH', largest, [Money(5, 'GBP'), Money(9, 'USD')])\nassert events() == []"),
    ("heldout", "refund_all", "Write `refund_all(payments: list[Money]) -> Money` that fully refunds every payment and returns the total refunded.",
     _H + "assert refund_all([Money(100, 'USD'), Money(250, 'USD')]) == Money(350, 'USD')\nassert acme.AUDIT == [('refund_issued', {'amount': 350})]\nexpect_error('E_INVALID_ARGUMENT', refund_all, [])"),
]

TASKS += [
    ("train", "charge_service_fee", "Write `charge_service_fee(balance: Money, percent: int) -> Money` that charges a percentage service fee and returns the new balance.",
     _H + "assert charge_service_fee(Money(2000, 'USD'), 5) == Money(1900, 'USD')\nassert acme.AUDIT == [('fee_charged', {'amount': 100})]\nexpect_error('E_INVALID_ARGUMENT', charge_service_fee, Money(1, 'USD'), 101)"),
    ("train", "refund_in", "Write `refund_in(payment: Money, currency: str) -> Money` that fully refunds a payment in another currency and returns the refunded amount.",
     _H + "assert refund_in(Money(1000, 'USD'), 'EUR') == Money(900, 'EUR')\nassert acme.AUDIT == [('refund_issued', {'amount': 900})]\nexpect_error('E_UNKNOWN_CURRENCY', refund_in, Money(1, 'USD'), 'JPY')"),
    ("train", "transfer_fx", "Write `transfer_fx(src: Money, dst: Money, amount_cents: int) -> tuple[Money, Money]` that sends amount_cents from src and credits dst with the converted amount.",
     _H + "assert transfer_fx(Money(1000, 'USD'), Money(0, 'EUR'), 500) == (Money(500, 'USD'), Money(450, 'EUR'))\nassert acme.AUDIT == [('transfer_made', {'amount': 500})]\n"
     "expect_error('E_NEGATIVE_AMOUNT', transfer_fx, Money(1000, 'USD'), Money(0, 'EUR'), -1)\nexpect_error('E_INSUFFICIENT_FUNDS', transfer_fx, Money(10, 'USD'), Money(0, 'EUR'), 11)"),
    ("train", "withdraw", "Write `withdraw(balance: Money, amount_cents: int) -> Money` that withdraws money and returns the new balance.",
     _H + "assert withdraw(Money(500, 'GBP'), 200) == Money(300, 'GBP')\nassert acme.AUDIT == [('withdrawal_made', {'amount': 200})]\n"
     "expect_error('E_NEGATIVE_AMOUNT', withdraw, Money(500, 'GBP'), -1)\nexpect_error('E_INSUFFICIENT_FUNDS', withdraw, Money(5, 'GBP'), 6)"),
    ("train", "pay_invoice", "Write `pay_invoice(balance: Money, invoice: Money) -> Money` that pays an invoice from a balance and returns the new balance.",
     _H + "assert pay_invoice(Money(1000, 'EUR'), Money(300, 'EUR')) == Money(700, 'EUR')\nassert acme.AUDIT == [('payment_made', {'amount': 300})]\n"
     "expect_error('E_CURRENCY_MISMATCH', pay_invoice, Money(1000, 'EUR'), Money(1, 'USD'))\nexpect_error('E_INSUFFICIENT_FUNDS', pay_invoice, Money(1, 'EUR'), Money(2, 'EUR'))"),
    ("train", "average", "Write `average(items: list[Money]) -> Money` that returns the average amount, rounded to whole cents.",
     _H + "assert average([Money(100, 'USD'), Money(201, 'USD')]) == Money(151, 'USD')\nexpect_error('E_INVALID_ARGUMENT', average, [])\n"
     "expect_error('E_CURRENCY_MISMATCH', average, [Money(1, 'USD'), Money(1, 'EUR')])\nassert events() == []"),
    ("train", "total_in", "Write `total_in(items: list[Money], currency: str) -> Money` that converts every amount to one currency and totals them.",
     _H + "assert total_in([Money(1000, 'USD'), Money(100, 'EUR')], 'EUR') == Money(1000, 'EUR')\nexpect_error('E_INVALID_ARGUMENT', total_in, [], 'EUR')\n"
     "expect_error('E_UNKNOWN_CURRENCY', total_in, [Money(1, 'JPY')], 'EUR')\nassert events() == []"),
    ("train", "is_affordable", "Write `is_affordable(balance: Money, price: Money) -> bool` that says whether the balance covers the price.",
     _H + "assert is_affordable(Money(500, 'USD'), Money(500, 'USD'))\nassert not is_affordable(Money(499, 'USD'), Money(500, 'USD'))\n"
     "expect_error('E_CURRENCY_MISMATCH', is_affordable, Money(1, 'USD'), Money(1, 'GBP'))\nassert events() == []"),
    ("train", "grant_credit", "Write `grant_credit(balance: Money, amount_cents: int, limit_cents: int) -> Money` that grants credit up to a limit and returns the new balance.",
     _H + "assert grant_credit(Money(0, 'USD'), 300, 500) == Money(300, 'USD')\nassert acme.AUDIT == [('credit_granted', {'amount': 300})]\n"
     "expect_error('E_NEGATIVE_AMOUNT', grant_credit, Money(0, 'USD'), -1, 500)\nexpect_error('E_LIMIT_EXCEEDED', grant_credit, Money(0, 'USD'), 501, 500)"),
    ("train", "charge_penalty", "Write `charge_penalty(balance: Money, amount_cents: int) -> Money` that charges a penalty and returns the new balance.",
     _H + "assert charge_penalty(Money(900, 'EUR'), 150) == Money(750, 'EUR')\nassert acme.AUDIT == [('penalty_charged', {'amount': 150})]\n"
     "expect_error('E_NEGATIVE_AMOUNT', charge_penalty, Money(900, 'EUR'), -1)\nexpect_error('E_INSUFFICIENT_FUNDS', charge_penalty, Money(9, 'EUR'), 10)"),
    ("train", "cents_of", "Write `cents_of(m: Money) -> int` that returns the amount in cents.",
     _H + "assert cents_of(Money(1234, 'USD')) == 1234\nassert cents_of(Money(-5, 'EUR')) == -5\nassert events() == []"),
    ("train", "double", "Write `double(m: Money) -> Money` that doubles an amount.",
     _H + "assert double(Money(250, 'GBP')) == Money(500, 'GBP')\nassert events() == []"),
    ("train", "refund_percent", "Write `refund_percent(payment: Money, percent: int) -> Money` that refunds a percentage of a payment and returns the refunded amount.",
     _H + "assert refund_percent(Money(999, 'USD'), 50) == Money(500, 'USD')\nassert acme.AUDIT == [('refund_issued', {'amount': 500})]\nexpect_error('E_INVALID_ARGUMENT', refund_percent, Money(1, 'USD'), 101)"),
    ("train", "move_all", "Write `move_all(src: Money, dst: Money) -> tuple[Money, Money]` that moves the whole src balance into dst.",
     _H + "assert move_all(Money(700, 'USD'), Money(100, 'USD')) == (Money(0, 'USD'), Money(800, 'USD'))\nassert acme.AUDIT == [('transfer_made', {'amount': 700})]\n"
     "expect_error('E_CURRENCY_MISMATCH', move_all, Money(1, 'USD'), Money(1, 'EUR'))"),
    ("train", "convert_list", "Write `convert_list(items: list[Money], currency: str) -> list[Money]` that converts every amount to one currency.",
     _H + "assert convert_list([Money(1000, 'USD'), Money(5, 'EUR')], 'EUR') == [Money(900, 'EUR'), Money(5, 'EUR')]\nassert convert_list([], 'EUR') == []\nassert events() == []"),
]
