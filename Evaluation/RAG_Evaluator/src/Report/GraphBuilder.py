import pandas as pd
from bokeh.io import output_file, show, save
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.layouts import gridplot
from bokeh.embed import components
from collections import Counter
from bokeh.models import Div


def GraphBuilder(data, bar_color="#003566"):
    df = pd.DataFrame(data)

    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1 + 1e-10]
    labels = ['0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.4', '0.4-0.5', '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-0.9', '0.9-1']

    df = df.fillna(0)

    metrics = df.columns[1:].tolist()
    plots = []

    for metric in metrics:
        if metric not in df.columns or df[metric].isnull().all():
            continue

        df[metric] = df[metric].apply(lambda x: min(x, bins[-1] - 1e-10))

        binned_values = pd.cut(df[metric], bins=bins, labels=labels, include_lowest=True)
        value_counts = binned_values.value_counts().sort_index()

        p = figure(x_range=labels, height=400, width=400, title=f"Overall {metric}",
                   toolbar_location="above", tools="pan,wheel_zoom,box_zoom,reset,save")

        source = ColumnDataSource(
            data=dict(values=value_counts.index.tolist(), counts=value_counts.tolist()))
        p.vbar(x='values', top='counts', width=0.5, source=source, color=bar_color)

        hover = HoverTool(tooltips=[
            ("Range", "@values"),
            ("Count", "@counts")
        ])
        p.add_tools(hover)

        p.xgrid.grid_line_color = None
        p.y_range.start = 0
        p.xaxis.axis_label = metric
        p.yaxis.axis_label = "Count"

        plots.append(p)

    grid = gridplot(plots, ncols=3, sizing_mode='scale_width')
    overall_script, overall_div = components(grid)

    return overall_script, overall_div


def AllQtypeGraph(data, bar_color="#003566"):
    df = pd.DataFrame(data)

    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1 + 1e-10]
    labels = ['0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.4', '0.4-0.5', '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-0.9', '0.9-1']

    unique_question_types = df["question_type"].unique()
    metrics = df.columns[1:].tolist()

    all_scripts = {}
    all_divs = {}

    for q_type in unique_question_types:
        q_type_df = df[df["question_type"] == q_type].copy()
        plots = []

        for metric in metrics:
            q_type_df.loc[:, metric] = q_type_df[metric].apply(lambda x: min(x, bins[-1] - 1e-10))

            binned_values = pd.cut(q_type_df[metric], bins=bins, labels=labels, include_lowest=True)
            value_counts = binned_values.value_counts().sort_index()

            p = figure(x_range=labels, height=400, width=400, title=f"{metric} for {q_type}",
                       toolbar_location="above", tools="pan,wheel_zoom,box_zoom,reset,save")

            source = ColumnDataSource(data=dict(values=value_counts.index.tolist(), counts=value_counts.tolist()))
            p.vbar(x='values', top='counts', width=0.5, source=source, color=bar_color)

            hover = HoverTool(tooltips=[
                ("Range", "@values"),
                ("Count", "@counts")
            ])
            p.add_tools(hover)

            p.xgrid.grid_line_color = None
            p.y_range.start = 0
            p.xaxis.axis_label = metric
            p.yaxis.axis_label = "Count"

            plots.append(p)

        grid = gridplot(plots, ncols=3, sizing_mode='scale_width')
        script, div = components(grid)

        all_scripts[q_type] = script
        all_divs[q_type] = div

    return all_scripts, all_divs