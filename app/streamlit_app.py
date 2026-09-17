"""The analysis app: a thin shell over the modules in src/.

It shows what is loaded, how the data checks out, and performance by segment.
Verdicts on the candidate patterns arrive with ``validate.py``; until then the
app makes no claim about what works.

Run with:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import aggregations as agg
import checks
import loader

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
MAX_SERIES = agg.MAX_SERIES
assert len(SERIES_COLOURS) == MAX_SERIES

CURRENCY_SYMBOLS = {"EUR": "\u20ac", "GBP": "\u00a3", "USD": "$", "SEK": "kr"}
#: Written after the number ("218 kr"), not before it.
SUFFIX_CURRENCIES = frozenset({"SEK"})

#: Currencies an uploader can label their file with. A file whose currency
#: column names something else gets that added at the front of the list.
DISPLAY_CURRENCIES = ("EUR", "USD", "SEK")


currency_code = agg.currency_code


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


_by_period = agg.by_period


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
            st.caption("Problems are reported, never fixed automatically.")
    else:
        st.error(
            f"{len(report_checks.errors)} data check(s) failed — the numbers "
            "below cannot be trusted until this is fixed.",
            icon="🚨",
        )
        st.dataframe(table, width="stretch", hide_index=True)


SMALL_MULTIPLE_MIN_TURNOVER = agg.SMALL_MULTIPLE_MIN_TURNOVER
SMALL_MULTIPLE_MIN_BETS = agg.SMALL_MULTIPLE_MIN_BETS
_cumulative_by_slice = agg.cumulative_by_slice
_aggregate = agg.aggregate

#: The figures are computed in src/aggregations.py, shared with the API so
#: both apps show the same numbers. Streamlit only adds its cache on top.
_with_dimensions = st.cache_data(show_spinner=False)(agg.with_dimensions)

DIMENSIONS: dict[str, str] = {d.label: d.column for d in agg.DIMENSIONS}
SORT_LABELS: list[str] = [s.label for s in agg.SORTS]


def slice_columns(dim_label: str, code: str) -> dict:
    """Display config for an :func:`_aggregate` table. Shared by both views."""
    return {
        "slice": st.column_config.TextColumn(dim_label),
        "bets": st.column_config.NumberColumn("Bets", format="%d"),
        "fixtures": st.column_config.NumberColumn("Matches", format="%d"),
        "bets_per_fixture": st.column_config.NumberColumn(
            "Bets / match",
            format="%.2f",
            help=(
                "Average number of bets per match. Bets on the same match tend "
                "to win or lose together, so a high number means the group "
                "has less to say than its bet count suggests."
            ),
        ),
        "turnover": st.column_config.NumberColumn(
            f"Turnover ({code})", format="euro" if code == "EUR" else "%.2f"
        ),
        "pl": st.column_config.NumberColumn(
            f"P/L ({code})", format="euro" if code == "EUR" else "%.2f"
        ),
        "roi_pct": st.column_config.NumberColumn(
            "ROI %",
            format="%+.2f%%",
            help="Profit or loss as a share of the amount staked.",
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

# The integrity battery runs on every load and only makes noise when it has
# something to say: a failed check is a banner above every tab, because no
# figure below it can be trusted. Green checks are silent.
INTEGRITY = checks.run_checks(df)
if not INTEGRITY.ok:
    render_checks(INTEGRITY)

overview, upload, explore = st.tabs(["Overview", "Upload", "Explore"])

with overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Matched turnover ({CUR})", money(matched["turnover"].sum(), CUR))
    c2.metric(f"P/L ({CUR})", money(matched["pl"].sum(), CUR, signed=True))
    c3.metric("Fill rate", f"{loader.fill_rate(df):.1%}")
    c4.metric("Rows with odds info", f"{report.price_adjusted_coverage:.1%}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{report.n_rows:,}")
    c2.metric("Bets", f"{report.n_bets:,}")
    c3.metric("Matches", f"{report.n_fixtures:,}")
    c4.metric("Unmatched rows", f"{report.n_unmatched_rows:,}")

    st.subheader(f":blue[Cumulative P/L by month ({CUR})]")
    st.altair_chart(style_chart(cumulative_chart(matched, CUR)), width="stretch")

with upload:
    st.subheader(":blue[Check a new export]")
    st.caption(
        "Upload your own Sportmarket Pro export to see how it went. The file "
        "is checked, shown on its own and never added to the main dataset. "
        "One file shows what happened — it cannot tell you what works."
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
                "The currency your file is in. Taken from the file when it "
                "says so. Nothing is converted."
            ),
        )
        unit = d3.number_input(
            f"1 unit = ({chosen_cur})",
            min_value=0.01,
            value=round(loader.typical_stake(new), 2),
            step=1.0,
            help="Your typical stake in this file, unless you set another.",
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
        u4.metric("Matches", f"{new_report.n_fixtures:,}")
        st.caption(
            f"{new_report.n_rows:,} rows, "
            f"{new_report.date_min:%Y-%m-%d} to {new_report.date_max:%Y-%m-%d}. "
            f"{new_report.n_unmatched_rows:,} row(s) "
            f"({new_report.unmatched_row_share:.1%}) never got matched and are "
            "left out of the figures above."
        )

        st.subheader(f":blue[How this file ran ({new_cur})]")
        st.altair_chart(
            style_chart(cumulative_chart(new_matched, new_cur)), width="stretch"
        )
        st.altair_chart(
            style_chart(pl_bars_chart(new_matched, new_cur)), width="stretch"
        )
        st.caption(
            "Shown per day for short files, per month for longer ones. A few "
            "good or bad days in a row is normal — a coin flip does the same."
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
            "One file covers a short period, so each group is small. Check "
            "the number of matches before reading anything into the ROI."
        )



with explore:
    st.subheader(":blue[Segment explorer]")

    frame = _with_dimensions(matched)

    with st.expander("Filters", expanded=True):
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        day_min = frame["event_day"].min().date()
        day_max = frame["event_day"].max().date()
        span = fc1.date_input(
            "Match date range",
            (day_min, day_max),
            min_value=day_min,
            max_value=day_max,
        )
        stake_ceiling = agg.stake_ceiling(frame)
        min_stake = fc2.number_input(
            f"Minimum stake ({CUR})", min_value=0.0, value=0.0, step=0.5
        )
        max_stake = fc3.number_input(
            f"Maximum stake ({CUR})",
            min_value=0.0,
            value=stake_ceiling,
            step=0.5,
            help=f"Starts at the largest stake in the data ({stake_ceiling:,.0f}).",
        )
        fc4, fc5 = st.columns(2)
        pick_types = fc4.multiselect(
            "Market type", agg.option_values(frame, "market_type")
        )
        pick_books = fc5.multiselect("Bookie", agg.option_values(frame, "bookie"))

    # A half-picked date range (one click into the widget) means no date
    # filter yet, not an empty one.
    dates = span if isinstance(span, tuple) and len(span) == 2 else (None, None)
    try:
        frame = agg.apply_filters(
            frame,
            agg.Filters(
                date_from=dates[0],
                date_to=dates[1],
                min_stake=min_stake,
                max_stake=max_stake,
                market_types=tuple(pick_types),
                bookies=tuple(pick_books),
            ),
            stake_ceiling,
        )
    except agg.StakeRangeError as exc:
        st.warning(str(exc))
        st.stop()

    if frame.empty:
        st.warning("No rows match those filters.")
        st.stop()

    gc1, gc2, gc3 = st.columns([2, 2, 1])
    dim_label = gc1.selectbox("Group by", list(DIMENSIONS))
    sort_label = gc2.selectbox("Sort by", SORT_LABELS)
    min_fixtures = gc3.number_input("Min. matches", min_value=0, value=0, step=25)

    table_all = _aggregate(frame, DIMENSIONS[dim_label])
    table = table_all
    n_before = len(table)
    if min_fixtures:
        table = table[table["fixtures"] >= min_fixtures]
    table = agg.sort_table(table, agg.SORT_BY_LABEL[sort_label])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(f"Turnover in view ({CUR})", money(frame["turnover"].sum(), CUR))
    m2.metric(f"P/L in view ({CUR})", money(frame["pl"].sum(), CUR, signed=True))
    view_roi = 100 * frame["pl"].sum() / frame["turnover"].sum()
    m3.metric("ROI in view", f"{view_roi:+.2f}%")
    m4.metric("Bets in view", f"{int(frame['n_bets'].sum()):,}")
    m5.metric("Groups shown", f"{len(table)} of {n_before}")

    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config=slice_columns(dim_label, CUR),
    )

    top_n = st.slider("Groups to chart (largest first)", 3, 40, 12)
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
                alt.Tooltip("fixtures:Q", title="Matches", format=","),
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
    worth_a_curve = agg.eligible_for_curves(table_all)

    if worth_a_curve.empty:
        st.info(
            "No group here is big enough to chart (at least "
            f"{SMALL_MULTIPLE_MIN_TURNOVER:,.0f} units staked and "
            f"{SMALL_MULTIPLE_MIN_BETS:,} bets). Try another grouping or "
            "wider filters.",
            icon="🔍",
        )
    else:
        eligible = list(worth_a_curve["slice"])
        pc1, pc2 = st.columns([3, 1])
        picked = pc1.multiselect(
            "Groups to compare",
            eligible,
            default=eligible[:3],
            max_selections=MAX_SERIES,
            help=(
                f"Only groups with at least {SMALL_MULTIPLE_MIN_TURNOVER:,.0f} "
                f"units staked and {SMALL_MULTIPLE_MIN_BETS:,} bets are "
                f"listed ({len(eligible)} of {len(table_all)}). "
                f"Up to {MAX_SERIES} at a time so the colours stay apart."
            ),
        )
        measure = pc2.radio(
            "Measure",
            [f"Cumulative P/L ({CUR})", "Cumulative ROI %"],
            help=(
                "P/L favours big groups — more bets, more profit. ROI shows "
                "the return on what was staked, so groups of any size can be "
                "compared."
            ),
        )

        if not picked:
            st.info("Pick at least one group.", icon="👆")
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
                "ROI swings a lot in the first months, when only a few bets "
                "have been placed. That settles as the bets add up."
            )
