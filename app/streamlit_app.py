"""The analysis app: a thin shell over the modules in src/.

It shows what is loaded, how the data checks out, performance by segment, and
which candidate patterns are queued for testing. Panels backed by a module
that is not written yet say so instead of inventing a number.

Run with:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import checks  # noqa: E402
import loader  # noqa: E402

st.set_page_config(
    page_title="Sportmarket analysis",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(show_spinner=False)
def _load(data_dir: str) -> pd.DataFrame:
    return loader.load_raw(data_dir)


#: Chart ink, from the data-viz reference palette (dark instance). The
#: diverging pair is blue<->red, not red<->green: red/green is the conventional
#: profit/loss pairing and the one that collapses under the commonest colour
#: blindness. Validated against this surface — CVD ΔE 19.2 (protan),
#: normal-vision ΔE 29.0, both marks >= 3:1 contrast.
SURFACE = "#1a1a19"
GRID = "#2c2c2a"
BASELINE = "#383835"
INK_MUTED = "#898781"
INK_SECONDARY = "#c3c2b7"
POSITIVE = "#3987e5"
NEGATIVE = "#e66767"

#: The one accent in the app. Same hex as ``POSITIVE`` and as ``primaryColor``
#: in .streamlit/config.toml, so the title, the slider track and the profit
#: bars are literally one colour. Streamlit's own ``:blue[...]`` markdown is a
#: lighter text step and does not match, which is why the heading is coloured
#: with explicit CSS instead.
ACCENT = POSITIVE

#: Categorical slots for the segment comparison, in the fixed order the
#: data-viz reference palette prescribes — the ordering is the colour-blindness
#: safety mechanism, not decoration, so slots are assigned in sequence and
#: never cycled. Validated against this surface: worst adjacent CVD ΔE 8.4
#: (protan), normal-vision ΔE 19.3, all eight >= 3:1 contrast. Eight is the
#: hard ceiling; a ninth series would have to fold into "Other".
SERIES_COLOURS: list[str] = [
    "#3987e5",  # blue
    "#d95926",  # orange
    "#199e70",  # aqua
    "#c98500",  # yellow
    "#d55181",  # magenta
    "#008300",  # green
    "#9085e9",  # violet
    "#e66767",  # red
]
MAX_SERIES = len(SERIES_COLOURS)

CURRENCY_SYMBOLS = {"EUR": "\u20ac", "GBP": "\u00a3", "USD": "$", "SEK": "kr"}
#: Written after the number ("218 kr"), not before it.
SUFFIX_CURRENCIES = frozenset({"SEK"})

#: Currencies an uploader can label their file with. A file whose currency
#: column names something else gets that added at the front of the list.
DISPLAY_CURRENCIES = ("EUR", "USD", "SEK")


def currency_code(frame: pd.DataFrame) -> str:
    """The currency the amounts are in, read from the data rather than assumed.

    ``checks.check_single_currency`` guarantees there is only one, so taking the
    first is safe — and if a future export ever mixes currencies, that check
    fails loudly above the tabs before this label can mislead anyone.
    """
    if "currency" in frame.columns:
        values = frame["currency"].dropna().unique()
        if len(values) == 1:
            code = str(values[0])
            return code if code == "units" else code.upper()
    return "EUR"


def money(value: float, code: str, decimals: int = 0, signed: bool = False) -> str:
    """Format an amount so the currency is never in doubt.

    ``signed`` on P/L: a bare "1,204" reads as a number, "+€1,204" reads as a
    result. Filters can push any slice negative, so the sign carries meaning.
    """
    sign = "+" if signed and value >= 0 else "-" if signed and value < 0 else ""
    symbol = CURRENCY_SYMBOLS.get(code)
    magnitude = abs(value) if signed else value
    number = f"{magnitude:,.{decimals}f}"
    if symbol and code in SUFFIX_CURRENCIES:
        return f"{sign}{number} {symbol}"
    if symbol:
        return f"{sign}{symbol}{number}"
    if code == "units":
        return f"{sign}{number} u"
    return f"{sign}{number} {code}"


def style_chart(chart: alt.Chart) -> alt.Chart:
    """Recessive grid and axes, ink in text tokens rather than series colour."""
    return (
        chart.configure_view(strokeWidth=0, fill=SURFACE)
        .configure_axis(
            grid=True,
            gridColor=GRID,
            gridWidth=1,
            domainColor=BASELINE,
            tickColor=BASELINE,
            labelColor=INK_MUTED,
            titleColor=INK_SECONDARY,
            labelFontSize=11,
            titleFontSize=12,
            titleFontWeight="normal",
        )
        .configure_legend(
            labelColor=INK_SECONDARY,
            titleColor=INK_SECONDARY,
            labelFontSize=12,
            symbolType="square",
            symbolSize=140,
        )
    )


#: Below this span a frame is bucketed by day rather than by month. A fresh
#: export covers days, not years: bucketed monthly it collapses to a single
#: point, and an area chart with one point draws nothing at all.
DAILY_BUCKET_MAX_SPAN = pd.Timedelta(days=92)


def _by_period(frame: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    """Turnover, P/L and running P/L per bucket, plus how to label a bucket."""
    span = frame["event_day"].max() - frame["event_day"].min()
    # Two formats per resolution: the axis gets the short one (a daily axis
    # repeating the same year on every tick just collides with itself), the
    # tooltip the unambiguous one.
    freq, fmt, tick_fmt, label = (
        ("D", "%d %b %Y", "%d %b", "Day")
        if span <= DAILY_BUCKET_MAX_SPAN
        else ("M", "%b %Y", "%b %Y", "Month")
    )
    out = (
        frame.assign(period=frame["event_day"].dt.to_period(freq))
        .groupby("period", as_index=False)[["turnover", "pl"]]
        .sum()
    )
    out["period"] = out["period"].dt.to_timestamp()
    out["cumulative_pl"] = out["pl"].cumsum()
    out["label"] = out["period"].dt.strftime(fmt)
    out["tick"] = out["period"].dt.strftime(tick_fmt)
    return out, tick_fmt, label


def cumulative_chart(frame: pd.DataFrame, code: str) -> alt.Chart:
    """Cumulative P/L over time — a lifetime by month, one export by day."""
    data, tick_fmt, label = _by_period(frame)
    # Straight segments below a dozen buckets: monotone smoothing between four
    # daily points invents a shape the data has nothing to say about.
    interpolate = "monotone" if len(data) > 12 else "linear"
    # An area anchored at zero fills between the curve and the baseline, and
    # the gradient runs one way only. On a curve that dips below zero the fill
    # lands *above* the line and a losing week reads as a solid block of
    # profit-blue. Where that can happen, drop to a line — the same ink, no
    # claim about which side of zero the mass is on.
    ever_negative = bool((data["cumulative_pl"] < 0).any())
    # Buckets stay drawn when there are few of them: over a week the curve is
    # four or five points and the line alone hides how little is behind it.
    point = {"color": POSITIVE, "size": 55} if len(data) <= 40 else False
    if ever_negative:
        mark = alt.Chart(data).mark_line(
            interpolate=interpolate, strokeWidth=2, color=POSITIVE, point=point
        )
    else:
        mark = alt.Chart(data).mark_area(
            interpolate=interpolate,
            line={"color": POSITIVE, "strokeWidth": 2},
            point=point,
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color=SURFACE, offset=0),
                    alt.GradientStop(color=POSITIVE, offset=1),
                ],
                x1=1, x2=1, y1=1, y2=0,
            ),
        )
    chart = (
        mark.encode(
            x=alt.X(
                "period:T",
                title=None,
                # Left to itself Vega ticks a four-day domain every twelve
                # hours and, formatted as a date, prints each day twice.
                axis=alt.Axis(
                    format=tick_fmt,
                    tickCount=(
                        {"interval": "day", "step": 1}
                        if label == "Day"
                        else alt.Undefined
                    ),
                ),
            ),
            y=alt.Y("cumulative_pl:Q", title=f"Cumulative P/L ({code})"),
            tooltip=[
                alt.Tooltip("label:N", title=label),
                alt.Tooltip(
                    "cumulative_pl:Q", title=f"Cumulative ({code})", format=",.0f"
                ),
                alt.Tooltip("pl:Q", title=f"That {label.lower()} ({code})",
                            format="+,.0f"),
                alt.Tooltip("turnover:Q", title=f"Turnover ({code})", format=",.0f"),
            ],
        )
        .properties(height=320)
    )
    if not ever_negative:
        return chart
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color=BASELINE, strokeWidth=1)
        .encode(y="y:Q")
    )
    return chart + zero


def pl_bars_chart(frame: pd.DataFrame, code: str) -> alt.Chart:
    """P/L per bucket, signed. What a short export actually has to show.

    The cumulative curve answers "where did this end up"; over a handful of
    days that is one number and a slope. The bars answer "which days", which
    is the only question a week of betting can actually settle.
    """
    data, _, label = _by_period(frame)
    data = data.assign(
        direction=["Profit" if v >= 0 else "Loss" for v in data["pl"]]
    )
    bars = (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            # Ordinal, not temporal: on a time scale four daily bars are drawn
            # as four hairlines against a week of empty axis. A band scale
            # gives each bucket its share of the width, which is what a bar is
            # for. `sort=None` keeps the frame's own chronological order.
            x=alt.X("tick:N", title=None, sort=None,
                    axis=alt.Axis(labelAngle=0, labelLimit=110)),
            y=alt.Y("pl:Q", title=f"P/L ({code})"),
            color=alt.Color(
                "direction:N",
                scale=alt.Scale(domain=["Profit", "Loss"],
                                range=[POSITIVE, NEGATIVE]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("label:N", title=label),
                alt.Tooltip("pl:Q", title=f"P/L ({code})", format="+,.0f"),
                alt.Tooltip("turnover:Q", title=f"Turnover ({code})", format=",.0f"),
            ],
        )
        .properties(height=260)
    )
    zero = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color=BASELINE, strokeWidth=1)
        .encode(y="y:Q")
    )
    return bars + zero


def render_checks(report_checks: checks.CheckReport) -> None:
    """Show what the integrity battery found: a footnote when it passed, a
    banner and the full table when it did not.

    Same battery for the lifetime data and for a single uploaded file: a new
    export is worth nothing until it has passed the checks the old ones pass.
    """
    table = pd.DataFrame(
        [
            {
                "": ""
                if c.severity is checks.Severity.INFO
                else ("ok" if c.passed else "FAIL"),
                "Severity": c.severity.value,
                "Check": c.name,
                "Detail": c.detail,
            }
            for c in report_checks.checks
        ]
    )
    if report_checks.ok:
        n_warn = len(report_checks.warnings)
        with st.expander(
            f"{len(report_checks.checks)} integrity checks passed"
            + (f", {n_warn} warning(s)" if n_warn else "")
        ):
            st.dataframe(table, width="stretch", hide_index=True)
            st.caption("`checks.py` reports; it never repairs.")
    else:
        st.error(
            f"{len(report_checks.errors)} integrity check(s) failed — "
            "no figure below is trustworthy until this is resolved.",
            icon="🚨",
        )
        st.dataframe(table, width="stretch", hide_index=True)


#: A slice needs both to be worth its own cumulative curve. Turnover alone
#: lets a handful of huge bets in; bet count alone lets a long tail of tiny
#: ones in. Requiring both keeps the grid to the segments that actually have a
#: history to show.
SMALL_MULTIPLE_MIN_TURNOVER = 350.0  # units; roughly 0.3% of lifetime turnover
SMALL_MULTIPLE_MIN_BETS = 2_000


def _cumulative_by_slice(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Monthly running ROI per slice, for the small-multiple grid.

    Running **ROI**, not running P/L in currency: a large segment draws a tall
    P/L curve merely by being large, which compares size rather than skill.
    ``cumsum(pl) / cumsum(turnover)`` puts every segment on the same axis, and
    the shape carries the information — a real edge settles onto a positive
    number, noise keeps wandering.
    """
    monthly = (
        frame.assign(month=frame["event_day"].dt.to_period("M"))
        .groupby([column, "month"], observed=True, dropna=False)[["turnover", "pl"]]
        .sum()
        .reset_index()
        .rename(columns={column: "slice"})
    )
    monthly["slice"] = monthly["slice"].astype("string").fillna("(no value)")
    monthly["month"] = monthly["month"].dt.to_timestamp()
    monthly = monthly.sort_values(["slice", "month"])
    grouped = monthly.groupby("slice", observed=True)
    monthly["cum_pl"] = grouped["pl"].cumsum()
    monthly["cum_turnover"] = grouped["turnover"].cumsum()
    monthly["cum_roi_pct"] = 100 * monthly["cum_pl"] / monthly["cum_turnover"]
    return monthly


#: Dimensions the explorer can group by. Raw export columns first, then bins
#: derived here for presentation only — they are not analysis features and do
#: not belong in ``features.py``.
DIMENSIONS: dict[str, str] = {
    "Market type": "market_type",
    "Selection": "selection",
    "Bookie": "bookie",
    "Country": "country",
    "Competition": "competition",
    "Market (sport / period)": "market",
    "Event type": "event_type",
    "Stake bucket": "_stake_bucket",
    "Bets aggregated on the row": "_n_bets_bucket",
    "Year": "_year",
    "Month": "_month",
    "Weekday": "_weekday",
}

SORTS: dict[str, tuple[str, bool]] = {
    "Turnover (largest first)": ("turnover", False),
    "ROI (best first)": ("roi_pct", False),
    "ROI (worst first)": ("roi_pct", True),
    "P/L (largest first)": ("pl", False),
    "Fixtures (most first)": ("fixtures", False),
    "Bets per fixture (most first)": ("bets_per_fixture", False),
    "Name": ("slice", True),
}

#: In units, where 1 is the typical stake: a quarter of matched rows sit
#: below 0.5, half below 1, nine in ten below 3.5.
STAKE_BINS = [0, 0.5, 1, 2, 3, 5, 10, float("inf")]
STAKE_LABELS = ["<0.5", "0.5-1", "1-2", "2-3", "3-5", "5-10", "10+"]

@st.cache_data(show_spinner=False)
def _with_dimensions(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the presentation-only bins the explorer offers."""
    out = frame.copy()
    out["_year"] = out["event_day"].dt.year.astype("string")
    out["_month"] = out["event_day"].dt.to_period("M").astype("string")
    out["_weekday"] = out["event_day"].dt.day_name().astype("string")
    out["_stake_bucket"] = pd.cut(
        out["stake"], bins=STAKE_BINS, labels=STAKE_LABELS, right=False
    )
    out["_n_bets_bucket"] = pd.cut(
        out["n_bets"], bins=[0, 1, 2, float("inf")], labels=["1", "2", "3+"]
    )
    return out


def _aggregate(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Turnover, P/L and ROI per slice.

    ``dropna=False`` on purpose: a material share of rows carry no
    ``selection``, and they need not perform like the rest. Dropping them
    quietly would change every total that touches the column without saying so.
    """
    grouped = (
        frame.groupby(column, observed=True, dropna=False)
        .agg(
            bets=("n_bets", "sum"),
            fixtures=("fixture_id", "nunique"),
            turnover=("turnover", "sum"),
            pl=("pl", "sum"),
        )
        .reset_index()
        .rename(columns={column: "slice"})
    )
    grouped["slice"] = grouped["slice"].astype("string").fillna("(no value)")
    # Turnover-weighted: sum(pl) / sum(turnover), which is what the export's own
    # ROI column measures per row. The unweighted mean of that column is a
    # different number — small stakes are many and can pull it far from the
    # turnover-weighted figure — so averaging rows instead of weighting by
    # turnover is wrong, not merely imprecise.
    grouped["roi_pct"] = 100 * grouped["pl"] / grouped["turnover"]
    # Bets on one fixture win or lose together (CLAUDE.md rule 1), so this is
    # roughly the factor by which the slice's bet count overstates how much
    # independent information it carries. It is also the column that will drive
    # the width of the interval once stats.py resamples fixtures rather than
    # rows. Computed after the aggregation because division is not an
    # aggregation: .agg() collapses one column per group, this combines two
    # results that already exist.
    grouped["bets_per_fixture"] = grouped["bets"] / grouped["fixtures"]
    # Explicit order rather than assignment order: bets_per_fixture belongs
    # beside the fixture count it is derived from, not wherever it happened to
    # be computed.
    return grouped[
        ["slice", "bets", "fixtures", "bets_per_fixture", "turnover", "pl", "roi_pct"]
    ]


def slice_columns(dim_label: str, code: str) -> dict:
    """Display config for an :func:`_aggregate` table. Shared by both views."""
    return {
        "slice": st.column_config.TextColumn(dim_label),
        "bets": st.column_config.NumberColumn("Bets", format="%d"),
        "fixtures": st.column_config.NumberColumn("Fixtures", format="%d"),
        "bets_per_fixture": st.column_config.NumberColumn(
            "Bets / fixture",
            format="%.2f",
            help=(
                "How many bets sit on the average fixture in this slice. "
                "Bets on one fixture win or lose together, so a high number "
                "means the slice carries less independent information than "
                "its bet count suggests."
            ),
        ),
        "turnover": st.column_config.NumberColumn(
            f"Turnover ({code})", format="euro" if code == "EUR" else "localized"
        ),
        "pl": st.column_config.NumberColumn(
            f"P/L ({code})", format="euro" if code == "EUR" else "localized"
        ),
        "roi_pct": st.column_config.NumberColumn(
            "ROI %",
            format="%+.2f%%",
            help="Turnover-weighted: sum(P/L) / sum(turnover)",
        ),
    }


st.markdown(
    # A bare `h1` selector loses to Streamlit's own theme rule, which is
    # generated as a class+descendant selector (higher specificity than a
    # plain element selector) and would otherwise repaint it white in dark
    # mode. Target the actual heading container and force it.
    f"""<style>
    div[data-testid="stHeadingWithActionElements"] h1 {{
        color: {ACCENT} !important;
    }}
    </style>""",
    unsafe_allow_html=True,
)
st.title("Sportmarket analysis")
st.caption(
    "Candidate patterns, one battery, every verdict reported. "
    "The rejections are the content."
)

# The app reads data/processed/ only: the exports rescaled to notional units
# by ``python src/loader.py``, with the unit itself kept off disk. The raw EUR
# files never need to be where the app runs, and there is no toggle that could
# show them (CLAUDE.md -> Privacy).
try:
    df = _load(str(loader.DEFAULT_PROCESSED_DIR))
except FileNotFoundError:
    st.warning(
        "No processed data. On the machine that holds the raw exports, run "
        "`python src/loader.py` to write `data/processed/` in units, then "
        "deploy that directory.",
        icon="📄",
    )
    st.stop()

matched = loader.matched(df)
report = loader.describe(df)
CUR = currency_code(df)

# The integrity battery runs on every load but only makes noise when it has
# something to say. Green checks are a footnote at the end of Overview; a
# failed one is a banner above every tab, because no figure below it can be
# trusted.
INTEGRITY = checks.run_checks(df)
if not INTEGRITY.ok:
    render_checks(INTEGRITY)

overview, upload, explore, findings = st.tabs(
    ["Overview", "Upload", "Explore", "Findings"]
)

with overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Matched turnover ({CUR})", money(matched["turnover"].sum(), CUR))
    c2.metric(f"P/L ({CUR})", money(matched["pl"].sum(), CUR, signed=True))
    c3.metric("Fill rate", f"{loader.fill_rate(df):.1%}")
    c4.metric("Price-adj. turnover present", f"{report.price_adjusted_coverage:.1%}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{report.n_rows:,}")
    c2.metric("Bets", f"{report.n_bets:,}")
    c3.metric("Fixtures", f"{report.n_fixtures:,}")
    c4.metric("Unmatched rows", f"{report.n_unmatched_rows:,}")
    st.caption(
        "Point estimates only — an interval requires `stats.py`. "
        "Unmatched rows (turnover = 0) are excluded from turnover and P/L. "
        "Price-adj. turnover is column presence (2025 onwards), **not** "
        "exact-odds coverage: splitting exact from censored needs `odds.py`."
    )

    st.subheader(f":blue[Cumulative P/L by month ({CUR})]")
    st.altair_chart(style_chart(cumulative_chart(matched, CUR)), width="stretch")

    if INTEGRITY.ok:
        render_checks(INTEGRITY)

with upload:
    st.subheader(":blue[Check a new export]")
    st.caption(
        "Run a Sportmarket Pro CSV — yours or anyone's — through the same "
        "loader and the same integrity battery the archived exports pass, and "
        "see it on its own. It never joins the main dataset. **Descriptive "
        "only** — one file is a look at what happened, not evidence about "
        "what works."
    )

    file = st.file_uploader("Sportmarket Pro export (CSV)", type="csv")
    if file is None:
        st.info("No file loaded.", icon="📄")
    else:
        try:
            # SchemaError is a ValueError; so are pandas' own parse failures.
            new = loader.load_upload(file, file.name)
        except ValueError as exc:
            new = None
            st.error(str(exc), icon="🚨")

    if file is not None and new is not None:
        render_checks(checks.run_checks(new))
        # The uploader chooses how to see their own money. Units by default,
        # like the rest of the app; the currency view shows the file's amounts
        # as they are, labelled with the currency the file says it is in. No
        # conversion happens anywhere — a different label is the viewer's call.
        file_cur = currency_code(new)
        options = [c for c in DISPLAY_CURRENCIES if c != file_cur]
        if file_cur != "units":
            options.insert(0, file_cur)
        d1, d2, d3 = st.columns(3)
        display = d1.radio(
            "Show amounts in", ["Units", "Currency"], horizontal=True
        )
        chosen_cur = d2.selectbox(
            "Currency",
            options,
            help=(
                "Pre-filled from the file's `Customer currency` column when it "
                "has one. Nothing is converted: pick what the file is in."
            ),
        )
        unit = d3.number_input(
            f"1 unit = ({chosen_cur})",
            min_value=0.01,
            value=round(loader.typical_stake(new), 2),
            step=1.0,
            help="Median matched stake in this file by default.",
            disabled=display != "Units",
        )
        if display == "Units":
            new = loader.to_units(new, unit)
            new_cur = "units"
        else:
            new_cur = chosen_cur
        new_matched = loader.matched(new)
        new_report = loader.describe(new)

        u1, u2, u3, u4 = st.columns(4)
        u1.metric(
            f"Matched turnover ({new_cur})",
            money(new_matched["turnover"].sum(), new_cur),
        )
        u2.metric(
            f"P/L ({new_cur})",
            money(new_matched["pl"].sum(), new_cur, signed=True),
        )
        u3.metric("Bets", f"{new_report.n_bets:,}")
        u4.metric("Fixtures", f"{new_report.n_fixtures:,}")
        st.caption(
            f"{new_report.n_rows:,} rows, "
            f"{new_report.date_min:%Y-%m-%d} .. {new_report.date_max:%Y-%m-%d}. "
            f"{new_report.n_unmatched_rows:,} unmatched row(s) "
            f"({new_report.unmatched_row_share:.1%}) excluded from the figures "
            "above. Price-adjusted turnover present on "
            f"{new_report.price_adjusted_coverage:.1%} of rows."
        )

        st.subheader(f":blue[How this file ran ({new_cur})]")
        st.altair_chart(
            style_chart(cumulative_chart(new_matched, new_cur)), width="stretch"
        )
        st.altair_chart(
            style_chart(pl_bars_chart(new_matched, new_cur)), width="stretch"
        )
        st.caption(
            "Bucketed by day when the export covers less than a quarter, by "
            "month when it covers more. A week of fixtures is a handful of "
            "buckets, so the run of good and bad days is the whole picture — "
            "and a run that short is what a coin flip looks like too."
        )

        st.subheader(":blue[Breakdown]")
        upload_dim = st.selectbox("Group by", list(DIMENSIONS), key="upload_dim")
        st.dataframe(
            _aggregate(
                _with_dimensions(new_matched), DIMENSIONS[upload_dim]
            ).sort_values("turnover", ascending=False),
            width="stretch",
            hide_index=True,
            column_config=slice_columns(upload_dim, new_cur),
        )
        st.caption(
            "A single export covers months, not years, so every slice here is "
            "thin — read the `fixtures` column before reading the ROI beside "
            "it. Nothing on this tab has an interval or an out-of-sample check."
        )



with explore:
    st.subheader(":blue[Segment explorer]")

    frame = _with_dimensions(matched)

    with st.expander("Filters", expanded=True):
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        day_min = frame["event_day"].min().date()
        day_max = frame["event_day"].max().date()
        span = fc1.date_input(
            "Fixture date range",
            (day_min, day_max),
            min_value=day_min,
            max_value=day_max,
        )
        # Ceiling to a whole unit so the default sits at or above every row and
        # the filter starts out excluding nothing.
        stake_ceiling = float(math.ceil(frame["stake"].max()))
        min_stake = fc2.number_input(
            f"Minimum stake ({CUR})", min_value=0.0, value=0.0, step=0.5
        )
        max_stake = fc3.number_input(
            f"Maximum stake ({CUR})",
            min_value=0.0,
            value=stake_ceiling,
            step=0.5,
            help=(
                f"Defaults to the largest stake in the data ({stake_ceiling:,.0f}), "
                "so it starts out excluding nothing."
            ),
        )
        fc4, fc5 = st.columns(2)
        pick_types = fc4.multiselect(
            "Market type",
            sorted(str(v) for v in frame["market_type"].dropna().unique()),
        )
        pick_books = fc5.multiselect(
            "Bookie", sorted(str(v) for v in frame["bookie"].dropna().unique())
        )

    if isinstance(span, tuple) and len(span) == 2:
        frame = frame[
            (frame["event_day"] >= pd.Timestamp(span[0]))
            & (frame["event_day"] <= pd.Timestamp(span[1]))
        ]
    if max_stake < min_stake:
        st.warning(
            f"Maximum stake ({max_stake:,.2f}) is below the minimum "
            f"({min_stake:,.2f}) — no row can satisfy both."
        )
        st.stop()
    if min_stake:
        frame = frame[frame["stake"] >= min_stake]
    if max_stake < stake_ceiling:
        frame = frame[frame["stake"] <= max_stake]
    if pick_types:
        frame = frame[frame["market_type"].astype("string").isin(pick_types)]
    if pick_books:
        frame = frame[frame["bookie"].astype("string").isin(pick_books)]

    if frame.empty:
        st.warning("No rows match those filters.")
        st.stop()

    gc1, gc2, gc3 = st.columns([2, 2, 1])
    dim_label = gc1.selectbox("Group by", list(DIMENSIONS))
    sort_label = gc2.selectbox("Sort by", list(SORTS))
    min_fixtures = gc3.number_input("Min fixtures", min_value=0, value=0, step=25)

    table_all = _aggregate(frame, DIMENSIONS[dim_label])
    table = table_all
    n_before = len(table)
    if min_fixtures:
        table = table[table["fixtures"] >= min_fixtures]
    sort_col, ascending = SORTS[sort_label]
    table = table.sort_values(sort_col, ascending=ascending)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(f"Turnover in view ({CUR})", money(frame["turnover"].sum(), CUR))
    m2.metric(f"P/L in view ({CUR})", money(frame["pl"].sum(), CUR, signed=True))
    view_roi = 100 * frame["pl"].sum() / frame["turnover"].sum()
    m3.metric("ROI in view", f"{view_roi:+.2f}%")
    m4.metric("Bets in view", f"{int(frame['n_bets'].sum()):,}")
    m5.metric("Slices shown", f"{len(table)} of {n_before}")

    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config=slice_columns(dim_label, CUR),
    )
    st.caption(
        f"{n_before} slice(s) before the fixture filter. Scanning that many at "
        "the 95% level produces roughly "
        f"{0.05 * n_before:.1f} false positives by construction — which is why "
        "the number is printed here rather than left for you to remember."
    )

    top_n = st.slider("Slices to chart (by turnover)", 3, 40, 12)
    chart_data = table.nlargest(min(top_n, len(table)), "turnover").copy()
    chart_data["direction"] = [
        "Profit" if v >= 0 else "Loss" for v in chart_data["pl"]
    ]
    order = list(chart_data["slice"])

    bars = (
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "slice:N",
                sort=order,
                title=None,
                axis=alt.Axis(labelAngle=-40, labelLimit=150),
            ),
            y=alt.Y("roi_pct:Q", title="ROI % (turnover-weighted)"),
            color=alt.Color(
                "direction:N",
                scale=alt.Scale(
                    domain=["Profit", "Loss"], range=[POSITIVE, NEGATIVE]
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("slice:N", title=dim_label),
                alt.Tooltip("roi_pct:Q", title="ROI %", format="+.2f"),
                alt.Tooltip("turnover:Q", title=f"Turnover ({CUR})", format=",.0f"),
                alt.Tooltip("pl:Q", title=f"P/L ({CUR})", format="+,.0f"),
                alt.Tooltip("fixtures:Q", title="Fixtures", format=","),
                alt.Tooltip("bets:Q", title="Bets", format=","),
            ],
        )
        .properties(height=340)
    )
    zero_line = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color=BASELINE, strokeWidth=1)
        .encode(y="y:Q")
    )
    st.altair_chart(style_chart(bars + zero_line), width="stretch")

    # ------------------------------------------------------------------
    # Pick segments, plot their cumulative curves on one set of axes
    # ------------------------------------------------------------------
    st.subheader(":blue[Compare segments over time]")
    worth_a_curve = table_all[
        (table_all["turnover"] >= SMALL_MULTIPLE_MIN_TURNOVER)
        & (table_all["bets"] >= SMALL_MULTIPLE_MIN_BETS)
    ].sort_values("turnover", ascending=False)

    if worth_a_curve.empty:
        st.info(
            "No slice in this grouping clears both thresholds "
            f"({SMALL_MULTIPLE_MIN_TURNOVER:,.0f} turnover and "
            f"{SMALL_MULTIPLE_MIN_BETS:,} bets). Try a coarser dimension, "
            "or widen the filters.",
            icon="🔍",
        )
    else:
        eligible = list(worth_a_curve["slice"])
        pc1, pc2 = st.columns([3, 1])
        picked = pc1.multiselect(
            "Segments to plot",
            eligible,
            default=eligible[:3],
            max_selections=MAX_SERIES,
            help=(
                f"Slices with at least {SMALL_MULTIPLE_MIN_TURNOVER:,.0f} turnover "
                f"and {SMALL_MULTIPLE_MIN_BETS:,} bets — "
                f"{len(eligible)} of {len(table_all)} in this grouping. "
                f"Capped at {MAX_SERIES}: past that, no colour ordering stays "
                "distinguishable under colour blindness."
            ),
        )
        measure = pc2.radio(
            "Measure",
            [f"Cumulative P/L ({CUR})", "Cumulative ROI %"],
            help=(
                "P/L reads naturally but rewards size — a big segment climbs "
                "higher just by being big. ROI puts every segment on one axis "
                "and compares form instead of volume."
            ),
        )

        if not picked:
            st.info("Pick at least one segment.", icon="👆")
        else:
            field = "cum_pl" if measure.startswith("Cumulative P/L") else "cum_roi_pct"
            fmt = "+,.0f" if field == "cum_pl" else "+.2f"
            curves = _cumulative_by_slice(frame, DIMENSIONS[dim_label])
            curves = curves[curves["slice"].isin(picked)]

            tooltip = [
                alt.Tooltip("slice:N", title=dim_label),
                alt.Tooltip("month:T", title="Month", format="%b %Y"),
                alt.Tooltip(f"{field}:Q", title=measure, format=fmt),
                alt.Tooltip(
                    "cum_turnover:Q", title=f"Turnover to date ({CUR})", format=",.0f"
                ),
            ]
            x = alt.X("month:T", title=None)
            y = alt.Y(f"{field}:Q", title=measure)

            if len(picked) == 1:
                # One segment: the filled area reads best, and with a single
                # series the title names it — no legend needed.
                series = (
                    alt.Chart(curves)
                    .mark_area(
                        interpolate="monotone",
                        line={"color": ACCENT, "strokeWidth": 2},
                        color=alt.Gradient(
                            gradient="linear",
                            stops=[
                                alt.GradientStop(color=SURFACE, offset=0),
                                alt.GradientStop(color=ACCENT, offset=1),
                            ],
                            x1=1, x2=1, y1=1, y2=0,
                        ),
                    )
                    .encode(x=x, y=y, tooltip=tooltip)
                )
            else:
                # Several: lines, because stacked or overlapping fills stop
                # being readable the moment two segments cross.
                series = (
                    alt.Chart(curves)
                    .mark_line(interpolate="monotone", strokeWidth=2)
                    .encode(
                        x=x,
                        y=y,
                        color=alt.Color(
                            "slice:N",
                            title=None,
                            sort=picked,
                            scale=alt.Scale(
                                domain=picked,
                                range=SERIES_COLOURS[: len(picked)],
                            ),
                            legend=alt.Legend(orient="top"),
                        ),
                        tooltip=tooltip,
                    )
                )

            baseline_rule = (
                alt.Chart(pd.DataFrame({"y": [0]}))
                .mark_rule(color=BASELINE, strokeWidth=1)
                .encode(y="y:Q")
            )
            st.altair_chart(
                style_chart((series + baseline_rule).properties(height=380)),
                width="stretch",
            )
            st.caption(
                "Early months swing hard on the ROI measure because the "
                "denominator is still small — that is sample size showing, not "
                "a change in form."
            )

with findings:
    st.subheader(":blue[Candidate patterns]")
    st.table(
        pd.DataFrame(
            [
                ("log(stake)", "behavioural", "not yet tested"),
                ("n_bets_on_position ≥ 2", "behavioural", "not yet tested"),
                ("both_sides_flag", "behavioural", "not yet tested"),
                ("is_under", "behavioural", "not yet tested"),
                ("Core vs novelty market types", "market", "not yet tested"),
                ("Differences among core market types", "market", "not yet tested"),
                ("Country", "segmentation", "not yet tested"),
                ("Competition", "segmentation", "not yet tested"),
                ("Bookie", "segmentation", "not yet tested"),
                ("Day of week, month", "calendar", "not yet tested"),
                ("Women's vs men's football, friendlies", "context", "not yet tested"),
                ("League familiarity", "context", "not yet tested"),
            ],
            columns=["Candidate", "Kind", "Verdict"],
        )
    )
    st.caption(
        "Every candidate gets a verdict — REPLICATES / INSUFFICIENT / NOISE — "
        "from the same battery, and every verdict is reported, including the "
        "rejections."
    )
    st.info(
        "**Verdicts per candidate** need `src/validate.py`, which is the repo "
        "owner's to write (CLAUDE.md → Division of labour). The panel appears "
        "once it lands.",
        icon="🚧",
    )
