"""
smart_data/visualizer.py
========================
Adaptive Visual Data Synthesizer for SMAR v2.
Automatically inspects any query or operation result and generates elegant,
dark-mode high-resolution charts and images (bar, donut, line, or KPI cards)
in Base64 PNG format, adapting dynamically to any tabular domain.
Zero hardcoding: works for sales, retail, hospital, parts, or custom datasets.
"""

import io
import base64
import logging
from typing import Dict, Any, List, Optional, Union

# Set non-interactive headless backend before importing pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

logger = logging.getLogger("smar.smart_data.visualizer")


class AdaptiveDataVisualizer:
    """
    Generates tailored, high-DPI dark-mode visual charts in Base64 PNG format
    adapting to any dataset shape.
    """

    # Modern dark theme color palette matching Next.js 15 UI
    BG_COLOR = "#0f172a"        # slate-900
    PANEL_COLOR = "#1e293b"     # slate-800
    TEXT_COLOR = "#f8fafc"      # slate-50
    MUTED_TEXT = "#94a3b8"      # slate-400
    GRID_COLOR = "#334155"      # slate-700
    
    PALETTE = [
        "#06b6d4",  # cyan-500
        "#8b5cf6",  # violet-500
        "#3b82f6",  # blue-500
        "#10b981",  # emerald-500
        "#f43f5e",  # rose-500
        "#f59e0b",  # amber-500
        "#ec4899",  # pink-500
        "#14b8a6",  # teal-500
    ]

    def _setup_figure_theme(self, fig, ax):
        """Applies consistent dark-mode styling to matplotlib figure and axes."""
        fig.patch.set_facecolor(self.BG_COLOR)
        if ax is not None:
            ax.set_facecolor(self.PANEL_COLOR)
            ax.tick_params(colors=self.MUTED_TEXT, labelsize=9)
            for spine in ax.spines.values():
                spine.set_color(self.GRID_COLOR)
                spine.set_linewidth(0.8)
            ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=self.GRID_COLOR)
            ax.xaxis.grid(False)

    def _to_base64_png(self, fig) -> str:
        """Converts matplotlib figure directly into a Base64 data URL string."""
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
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

        # 1. Aggregation with breakdown (grouped data) -> Bar Chart or Donut Chart
        if op_type == "AGGREGATION" and operation_result.get("breakdown"):
            breakdown = operation_result["breakdown"]
            table = operation_result.get("table", "Data").title()
            col = operation_result.get("column", "Value").replace("_", " ").title()
            grp = operation_result.get("group_by", "Group").replace("_", " ").title()
            fn = operation_result.get("function", "SUM")

            title = title_hint or f"{fn} of {col} by {grp} ({table})"

            # If 6 or fewer categories, check if donut chart is suitable
            if len(breakdown) <= 6 and fn in ["SUM", "COUNT"]:
                return self.generate_donut_chart(breakdown, title=title)
            else:
                return self.generate_bar_chart(breakdown, title=title, x_label=grp, y_label=f"{fn} of {col}")

        # 2. Single Aggregate Metric -> High-Impact KPI Card
        if op_type == "AGGREGATION":
            val = operation_result.get("value", 0)
            formatted = operation_result.get("formatted_value", str(val))
            fn = operation_result.get("function", "METRIC")
            col = operation_result.get("column", "Total").replace("_", " ").title()
            table = operation_result.get("table", "Records").title()
            rows_eval = operation_result.get("total_rows_evaluated", 0)

            title = title_hint or f"{fn} of {col}"
            subtitle = f"Evaluated across {rows_eval:,} rows in {table}" if rows_eval else f"Dataset: {table}"
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
        """Generates a sleek horizontal or vertical dark-mode bar chart."""
        fig, ax = plt.subplots(figsize=(8, 4.5))
        self._setup_figure_theme(fig, ax)

        keys = list(data.keys())[:12]  # Cap at top 12 items for clean display
        values = [data[k] for k in keys]
        colors = [self.PALETTE[i % len(self.PALETTE)] for i in range(len(keys))]

        # If labels are long, use horizontal bar chart
        long_labels = any(len(str(k)) > 7 for k in keys) or len(keys) > 6

        if long_labels:
            y_pos = range(len(keys))
            bars = ax.barh(y_pos, values, color=colors, edgecolor="none", height=0.6, alpha=0.9)
            ax.set_yticks(y_pos)
            ax.set_yticklabels([str(k) for k in keys], color=self.TEXT_COLOR, fontsize=9)
            ax.invert_yaxis()  # top-down
            if x_label:
                ax.set_xlabel(x_label, color=self.MUTED_TEXT, fontsize=10, labelpad=8)
            # Add data labels at bar ends
            max_v = max(values) if values else 1
            for b, val in zip(bars, values):
                fmt = f"{val:,.1f}" if isinstance(val, float) else f"{val:,}"
                ax.text(b.get_width() + (max_v * 0.02), b.get_y() + b.get_height()/2, fmt,
                        va="center", color=self.TEXT_COLOR, fontsize=8, fontweight="bold")
            ax.set_xlim(0, max_v * 1.18)
        else:
            x_pos = range(len(keys))
            bars = ax.bar(x_pos, values, color=colors, edgecolor="none", width=0.55, alpha=0.9)
            ax.set_xticks(x_pos)
            ax.set_xticklabels([str(k) for k in keys], color=self.TEXT_COLOR, fontsize=9)
            if y_label:
                ax.set_ylabel(y_label, color=self.MUTED_TEXT, fontsize=10, labelpad=8)
            # Add data labels above bars
            max_v = max(values) if values else 1
            for b, val in zip(bars, values):
                fmt = f"{val:,.1f}" if isinstance(val, float) else f"{val:,}"
                ax.text(b.get_x() + b.get_width()/2, b.get_height() + (max_v * 0.02), fmt,
                        ha="center", va="bottom", color=self.TEXT_COLOR, fontsize=8, fontweight="bold")
            ax.set_ylim(0, max_v * 1.18)

        ax.set_title(title, color=self.TEXT_COLOR, fontsize=13, fontweight="bold", pad=14)

        b64 = self._to_base64_png(fig)
        return {
            "image_base64": b64,
            "chart_type": "bar",
            "title": title,
            "description": f"Bar chart showing {title} across {len(keys)} items."
        }

    def generate_donut_chart(
        self,
        data: Dict[str, Union[int, float]],
        title: str = "Distribution"
    ) -> Dict[str, Any]:
        """Generates a modern donut chart for proportional data."""
        fig, ax = plt.subplots(figsize=(6, 4))
        self._setup_figure_theme(fig, None)

        labels = list(data.keys())
        values = [data[k] for k in labels]
        colors = [self.PALETTE[i % len(self.PALETTE)] for i in range(len(labels))]

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.75,
            wedgeprops=dict(width=0.45, edgecolor=self.BG_COLOR, linewidth=2),
            textprops=dict(color=self.TEXT_COLOR, fontsize=9)
        )

        for at in autotexts:
            at.set_color(self.TEXT_COLOR)
            at.set_fontsize(8)
            at.set_weight("bold")

        ax.set_title(title, color=self.TEXT_COLOR, fontsize=12, fontweight="bold", pad=12)

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
        """Generates a high-impact metric KPI card image."""
        fig, ax = plt.subplots(figsize=(6, 2.5))
        self._setup_figure_theme(fig, ax)
        ax.axis("off")

        # Decorative accent bar
        accent_rect = plt.Rectangle((0.05, 0.88), 0.08, 0.04, color=self.PALETTE[0], transform=ax.transAxes)
        ax.add_patch(accent_rect)

        # Title
        ax.text(0.16, 0.87, title.upper(), transform=ax.transAxes, color=self.MUTED_TEXT,
                fontsize=11, fontweight="bold", va="center")

        # Large Metric Value
        ax.text(0.05, 0.45, metric_value, transform=ax.transAxes, color=self.TEXT_COLOR,
                fontsize=28, fontweight="bold", va="center")

        # Subtitle
        if subtitle:
            ax.text(0.05, 0.15, subtitle, transform=ax.transAxes, color=self.MUTED_TEXT,
                    fontsize=9, va="center")

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
        """Generates a chart comparing records from a tabular query result."""
        if not records:
            return None

        first_rec = records[0]
        # Identify label column (name, title, id, tag)
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
