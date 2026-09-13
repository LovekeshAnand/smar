"""
smart_data/visualizer.py
========================
Adaptive Visual Data Synthesizer for SMAR.
Automatically inspects any query or operation result and generates elegant,
dark-mode high-resolution charts and images in Base64 PNG format,
strictly aligned with SMAR's cohesive purple enterprise design system.
Single-color palette ensures professional, non-distracting data presentations.
"""

import io
import base64
import logging
from typing import Dict, Any, List, Optional, Union

# Set non-interactive headless backend before importing pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

logger = logging.getLogger("smar.smart_data.visualizer")


class AdaptiveDataVisualizer:
    """
    Generates tailored, high-DPI dark-mode visual charts in Base64 PNG format
    using a cohesive, single-color purple theme matching SMAR's executive UI.
    """

    # Monochromatic Dark Purple Theme Tokens
    BG_COLOR = "#09090b"            # Deep zinc-950 canvas
    PANEL_COLOR = "#0f0d19"         # Midnight with subtle violet-zinc undertone
    TEXT_COLOR = "#ffffff"          # Pure white for high legibility
    MUTED_TEXT = "#a1a1aa"          # Zinc-400 for secondary metrics & axis labels
    GRID_COLOR = "#231f36"          # Soft purple-zinc gridline tint
    
    # Single Primary Purple Theme Color & Accents
    PRIMARY_PURPLE = "#8b5cf6"      # Main bar & visual color (Violet-500)
    HIGHLIGHT_PURPLE = "#a78bfa"    # Bar border stroke & badge tint (Violet-400)
    SOFT_PURPLE = "#c4b5fd"         # Data label highlight text (Violet-300)
    DEEP_PURPLE = "#6d28d9"         # Darker gradient anchor (Violet-700)

    # Monochromatic Purple Family for Multi-Category Distribution (Donut)
    MONOCHROME_PURPLE_SHADES = [
        "#8b5cf6",  # violet-500
        "#7c3aed",  # violet-600
        "#a78bfa",  # violet-400
        "#6d28d9",  # violet-700
        "#c4b5fd",  # violet-300
        "#5b21b6",  # violet-800
    ]

    def _setup_figure_theme(self, fig, ax=None):
        """Applies consistent dark-mode styling to matplotlib figure and axes."""
        fig.patch.set_facecolor(self.BG_COLOR)
        if ax is not None:
            ax.set_facecolor(self.PANEL_COLOR)
            ax.tick_params(colors=self.MUTED_TEXT, labelsize=9.5, width=0.8, length=4)
            # Hide top and right spines for a clean, borderless modern look
            if "top" in ax.spines:
                ax.spines["top"].set_visible(False)
            if "right" in ax.spines:
                ax.spines["right"].set_visible(False)
            if "left" in ax.spines:
                ax.spines["left"].set_color(self.GRID_COLOR)
                ax.spines["left"].set_linewidth(0.8)
            if "bottom" in ax.spines:
                ax.spines["bottom"].set_color(self.GRID_COLOR)
                ax.spines["bottom"].set_linewidth(0.8)

            ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=self.GRID_COLOR)
            ax.xaxis.grid(False)

    def _to_base64_png(self, fig) -> str:
        """Converts matplotlib figure directly into a Base64 data URL string."""
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=220,
            bbox_inches="tight",
            pad_inches=0.18,
            facecolor=fig.get_facecolor(),
            edgecolor="none"
        )
        plt.close(fig)
        buf.seek(0)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    def generate_chart_for_operation(
        self,
        operation_result: Dict[str, Any],
        title_hint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Dynamically analyzes an operation result (aggregation, breakdown, or tabular data)
        and generates the most informative visual chart.
        """
        op_type = operation_result.get("operation")

        # 1. Aggregation with breakdown (grouped data) -> Single-Color Purple Bar Chart
        if op_type == "AGGREGATION" and operation_result.get("breakdown"):
            breakdown = operation_result["breakdown"]
            table = operation_result.get("table", "Data").title()
            raw_col = str(operation_result.get("column", "*"))
            grp = operation_result.get("group_by", "Group").replace("_", " ").title()
            fn = operation_result.get("function", "SUM")

            if fn == "COUNT" and (raw_col == "*" or raw_col.lower().endswith("id") or raw_col == table.lower()):
                title = title_hint or f"{table} Count by {grp}"
                y_label = f"{table} Count"
            else:
                col = raw_col.replace("_", " ").title()
                title = title_hint or f"{fn} of {col} by {grp} ({table})"
                y_label = f"{fn} of {col}"

            # If 5 or fewer categories and sum/count, generate sleek monochromatic donut
            if len(breakdown) <= 5 and fn in ["SUM", "COUNT"] and "proportion" in (title_hint or "").lower():
                return self.generate_donut_chart(breakdown, title=title)
            else:
                return self.generate_bar_chart(breakdown, title=title, x_label=grp, y_label=y_label)

        # 2. Single Aggregate Metric -> High-Impact Purple KPI Card
        if op_type == "AGGREGATION":
            val = operation_result.get("value", 0)
            formatted = operation_result.get("formatted_value", str(val))
            fn = operation_result.get("function", "METRIC")
            raw_col = str(operation_result.get("column", "*"))
            table = operation_result.get("table", "Records").title()
            rows_eval = operation_result.get("total_rows_evaluated", 0)

            if fn == "COUNT" and (raw_col == "*" or raw_col.lower().endswith("id") or raw_col == table.lower()):
                title = title_hint or f"Total {table} Count"
            else:
                col = raw_col.replace("_", " ").title()
                title = title_hint or f"{fn} of {col}"
            subtitle = f"Evaluated across {rows_eval:,} verified records in {table}" if rows_eval else f"Warehouse Dataset: {table}"
            return self.generate_kpi_card(formatted, title=title, subtitle=subtitle)

        # 3. Tabular Query with multiple rows -> Multi-item Comparison Chart
        if op_type == "TABULAR" and operation_result.get("records"):
            records = operation_result["records"]
            table = operation_result.get("table", "Data").title()
            return self.generate_tabular_chart(records, table_name=table, title_hint=title_hint)

        return None

    def generate_bar_chart(
        self,
        data: Dict[str, Union[int, float]],
        title: str = "Data Overview",
        x_label: Optional[str] = None,
        y_label: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an executive, single-color purple dark-mode bar chart.
        All bars strictly use the single purple theme color with clean data labels.
        """
        fig, ax = plt.subplots(figsize=(8.2, 4.4))
        self._setup_figure_theme(fig, ax)

        keys = list(data.keys())[:10]  # Focus on top 10 items for maximum clarity
        values = [data[k] for k in keys]

        # Use single cohesive purple color across all bars
        bar_color = self.PRIMARY_PURPLE
        border_color = self.HIGHLIGHT_PURPLE

        # Decide orientation: long label names or many categories -> horizontal
        long_labels = any(len(str(k)) > 7 for k in keys) or len(keys) > 6

        if long_labels:
            y_pos = range(len(keys))
            bars = ax.barh(
                y_pos,
                values,
                color=bar_color,
                edgecolor=border_color,
                linewidth=1.2,
                height=0.55,
                alpha=0.92
            )
            ax.set_yticks(y_pos)
            ax.set_yticklabels([str(k) for k in keys], color=self.TEXT_COLOR, fontsize=9.5, fontweight="500")
            ax.invert_yaxis()  # Top-down order
            if x_label:
                ax.set_xlabel(x_label, color=self.MUTED_TEXT, fontsize=9.5, labelpad=8)

            # Data labels at the end of each bar
            max_v = max(values) if values else 1
            for b, val in zip(bars, values):
                fmt = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
                ax.text(
                    b.get_width() + (max_v * 0.02),
                    b.get_y() + b.get_height() / 2,
                    fmt,
                    va="center",
                    color=self.SOFT_PURPLE,
                    fontsize=8.5,
                    fontweight="bold"
                )
            ax.set_xlim(0, max_v * 1.20)
            ax.xaxis.grid(True, linestyle="--", alpha=0.25, color=self.GRID_COLOR)
            ax.yaxis.grid(False)
        else:
            x_pos = range(len(keys))
            bars = ax.bar(
                x_pos,
                values,
                color=bar_color,
                edgecolor=border_color,
                linewidth=1.2,
                width=0.52,
                alpha=0.92
            )
            ax.set_xticks(x_pos)
            ax.set_xticklabels([str(k) for k in keys], color=self.TEXT_COLOR, fontsize=9.5, fontweight="500")
            if y_label:
                ax.set_ylabel(y_label, color=self.MUTED_TEXT, fontsize=9.5, labelpad=8)

            # Data labels above each bar
            max_v = max(values) if values else 1
            for b, val in zip(bars, values):
                fmt = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
                ax.text(
                    b.get_x() + b.get_width() / 2,
                    b.get_height() + (max_v * 0.02),
                    fmt,
                    ha="center",
                    va="bottom",
                    color=self.SOFT_PURPLE,
                    fontsize=8.5,
                    fontweight="bold"
                )
            ax.set_ylim(0, max_v * 1.20)

        ax.set_title(title, color=self.TEXT_COLOR, fontsize=13, fontweight="bold", pad=18)

        b64 = self._to_base64_png(fig)
        return {
            "image_base64": b64,
            "chart_type": "bar",
            "title": title,
            "description": f"Visual breakdown for {title} across {len(keys)} categories."
        }

    def generate_donut_chart(
        self,
        data: Dict[str, Union[int, float]],
        title: str = "Distribution"
    ) -> Dict[str, Any]:
        """
        Generates a modern monochromatic purple donut chart.
        Uses coherent purple family gradients for proportion clarity without rainbow noise.
        """
        fig, ax = plt.subplots(figsize=(6.2, 4.2))
        self._setup_figure_theme(fig, None)

        labels = list(data.keys())
        values = [data[k] for k in labels]
        colors = [self.MONOCHROME_PURPLE_SHADES[i % len(self.MONOCHROME_PURPLE_SHADES)] for i in range(len(labels))]

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.74,
            wedgeprops=dict(width=0.42, edgecolor=self.BG_COLOR, linewidth=2.5),
            textprops=dict(color=self.TEXT_COLOR, fontsize=9, fontweight="500")
        )

        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontsize(8.5)
            at.set_weight("bold")

        ax.set_title(title, color=self.TEXT_COLOR, fontsize=13, fontweight="bold", pad=16, ha="center")

        b64 = self._to_base64_png(fig)
        return {
            "image_base64": b64,
            "chart_type": "donut",
            "title": title,
            "description": f"Donut chart showing proportion breakdown for {title}."
        }

    def generate_kpi_card(
        self,
        metric_value: str,
        title: str = "Metric",
        subtitle: str = ""
    ) -> Dict[str, Any]:
        """Generates a high-impact, purple-accented metric KPI card."""
        fig, ax = plt.subplots(figsize=(6.4, 2.6))
        self._setup_figure_theme(fig, ax)
        ax.axis("off")

        # Outer subtle purple accent border
        border_box = patches.FancyBboxPatch(
            (0.01, 0.01), 0.98, 0.98,
            boxstyle="round,pad=0.03,rounding_size=0.04",
            linewidth=1.2,
            edgecolor=self.DEEP_PURPLE,
            facecolor=self.PANEL_COLOR,
            transform=ax.transAxes
        )
        ax.add_patch(border_box)

        # Decorative vertical purple accent bar
        accent_bar = patches.Rectangle(
            (0.06, 0.22), 0.015, 0.58,
            color=self.PRIMARY_PURPLE,
            transform=ax.transAxes
        )
        ax.add_patch(accent_bar)

        # Eyebrow / Title
        ax.text(
            0.11, 0.78, title.upper(),
            transform=ax.transAxes,
            color=self.HIGHLIGHT_PURPLE,
            fontsize=10,
            fontweight="bold",
            va="center"
        )

        # Prominent Metric Value
        ax.text(
            0.11, 0.46, str(metric_value),
            transform=ax.transAxes,
            color=self.TEXT_COLOR,
            fontsize=26,
            fontweight="bold",
            va="center",
            parse_math=False
        )

        # Subtitle / Record context
        if subtitle:
            ax.text(
                0.11, 0.20, subtitle,
                transform=ax.transAxes,
                color=self.MUTED_TEXT,
                fontsize=8.5,
                va="center"
            )

        b64 = self._to_base64_png(fig)
        return {
            "image_base64": b64,
            "chart_type": "kpi",
            "title": title,
            "description": f"{title}: {metric_value}. {subtitle}"
        }

    def generate_tabular_chart(
        self,
        records: List[Dict[str, Any]],
        table_name: str = "Data",
        title_hint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generates a single-color purple chart comparing records from a tabular query result."""
        if not records:
            return None

        first_rec = records[0]
        # Identify label column (name, title, id, tag, city)
        label_col = next((k for k in first_rec.keys() if any(s in k.lower() for s in ["name", "title", "label", "city", "country", "category"])), None)
        if not label_col:
            label_col = next((k for k in first_rec.keys() if "id" in k.lower()), list(first_rec.keys())[0])

        # Identify primary numeric metric column
        numeric_cols = [k for k, v in first_rec.items() if isinstance(v, (int, float)) and not k.lower().endswith("_id") and k.lower() != "id"]
        if not numeric_cols:
            numeric_cols = [k for k, v in first_rec.items() if isinstance(v, (int, float))]

        if not numeric_cols:
            return None

        metric_col = numeric_cols[0]
        title = title_hint or f"{table_name}: {metric_col.replace('_', ' ').title()} by {label_col.replace('_', ' ').title()}"

        data_dict = {}
        for r in records[:10]:
            lbl = str(r.get(label_col, "Item"))
            val = r.get(metric_col, 0)
            if isinstance(val, (int, float)):
                data_dict[lbl] = val

        if data_dict:
            return self.generate_bar_chart(data_dict, title=title, x_label=metric_col.replace('_', ' ').title())
        return None
