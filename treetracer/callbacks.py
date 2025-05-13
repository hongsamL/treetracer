from dash import dcc, html, callback, Input, Output, State, no_update
from .plot_utils import *
import dash_mantine_components as dmc
import plotly.express as px
import json
import base64
import io
import pandas as pd


def register_callbacks(app, dataframes):
    # Sidebar collapse callback
    @callback(
        Output("appshell", "navbar"),
        Input("burger", "opened"),
        State("appshell", "navbar"),
    )
    def toggle_navbar(opened, navbar):
        navbar["collapsed"] = {"mobile": not opened}
        return navbar

    # Callback to handle file uploads
    @callback(
        [
            Output("uploaded-files-storage", "children"),
            Output("validation-alert", "title"),
            Output("validation-alert", "style"),
        ],
        Input("upload-data-button", "contents"),
        State("upload-data-button", "filename"),
        State("upload-data-button", "last_modified"),
        State("uploaded-files-storage", "children"),
        prevent_initial_call=True,
    )
    def update_uploaded_files(contents, filenames, dates, stored_data):
        if contents is None:
            return no_update, no_update, no_update

        # Initialize or get existing data from stored json in uploaded-files-storage Div
        if stored_data is None:
            file_data = []
        else:
            file_data = json.loads(stored_data)

        # Add new files if they don't already exist in the list
        existing_filenames = [item["filename"] for item in file_data]
        error_message = ""

        for i, (content, filename, date) in enumerate(zip(contents, filenames, dates)):
            # Check if file is a TSV
            if not filename.endswith(".tsv"):
                error_message = (
                    f"Only TSV files are allowed. '{filename}' was rejected."
                )
                continue

            if filename not in existing_filenames:
                try:
                    # Decode and parse the file content
                    content_type, content_string = content.split(",")
                    decoded = base64.b64decode(content_string)

                    # Read the TSV into a pandas DataFrame
                    df = pd.read_csv(io.StringIO(decoded.decode("utf-8")), sep="\t")
                    df.columns = [x.replace("V", "MDS") for x in df.columns]
                    mdscols = sorted([x for x in df.columns if "MDS" in x])
                    group_mapping = {
                        val: idx for idx, val in enumerate(df["group"].unique())
                    }
                    # categorical group
                    df["group_col"] = df["group"].map(group_mapping)
                    df["file"] = filename

                    # Renumber trees
                    df["treenum"] = df.groupby("group").cumcount() + 1
                    df["size"] = 6

                    # Store the DataFrame in our dictionary
                    dataframes[filename] = df

                    # Add file metadata to our storage
                    file_data.append(
                        {
                            "filename": filename,
                            "date": date,
                            "rows": len(df),
                            "dimensions": mdscols,
                            "groups": df["group"].unique().tolist(),
                            "MIN_TREENUM": int(df["treenum"].min()),
                            "MAX_TREENUM": int(df["treenum"].max()),
                        }
                    )
                except Exception as e:
                    error_message = f"Error processing {filename}: {str(e)}"
                    continue

        # Configure alert display based on error state
        alert_style = {"display": "block"} if error_message else {"display": "none"}

        return json.dumps(file_data), error_message, alert_style

    # Callback to update the MultiSelect with uploaded filenames
    @callback(
        Output("upload-placeholder", "children"),
        Input("uploaded-files-storage", "children"),
        prevent_initial_call=True,
    )
    def update_multiselect(stored_data):
        if not stored_data:
            return html.Div("No files uploaded yet.")

        file_data = json.loads(stored_data)

        if not file_data:
            return html.Div("No files uploaded yet.")

        # Get all filenames
        filenames = [item["filename"] for item in file_data]

        # Create the MultiSelect component
        multiselect = dmc.MultiSelect(
            id="files-multiselect",
            label="Uploaded TSV Files",
            description="Select files to process",
            data=filenames,
            value=filenames,  # Initially select all files
            style={"width": "100%"},
            dropdownOpened=True,
        )

        return multiselect

    # Callback to display information about selected files
    @callback(
        Output("data-info-display", "children", allow_duplicate=True),
        Input("files-multiselect", "value"),
        State("uploaded-files-storage", "children"),
        prevent_initial_call=True,
    )
    def display_file_info(selected_files, stored_data):
        if not selected_files or not stored_data:
            return html.Div("No files selected.")

        file_data = json.loads(stored_data)
        file_info = []

        for item in file_data:
            if item["filename"] in selected_files:
                df = dataframes.get(item["filename"])
                if df is not None:
                    file_info.append(
                        dmc.Paper(
                            children=[
                                dmc.Text(
                                    f"Filename: {item['filename']}",
                                ),
                                dmc.Text(
                                    f"Number of Dimensions: {len(item['dimensions'])}"
                                ),
                                dmc.Text(f"Dimensions: {item['dimensions']}"),
                                dmc.Text(f"Number of Groups: {len(item['groups'])}"),
                                dmc.Text("Groups: " + ", ".join(item["groups"])),
                                dmc.Text(
                                    f"Tree Range: {item['MIN_TREENUM']}-{item['MAX_TREENUM']}"
                                ),
                                dmc.Text(f"Total Number of Trees: {item['rows']}"),
                                dmc.Space(h=10),
                            ],
                            p="md",
                            shadow="xs",
                            withBorder=True,
                            mt=10,
                        )
                    )

        return html.Div(file_info)

    # Callback to clear uploaded files
    @callback(
        [
            Output("uploaded-files-storage", "children", allow_duplicate=True),
            Output("data-info-display", "children", allow_duplicate=True),
            Output("plot-display", "children", allow_duplicate=True),
        ],
        Input("clear-data-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_uploads(n_clicks):
        if n_clicks:
            # Clear the dataframes dictionary
            dataframes.clear()
            return (
                json.dumps([]),
                html.Div("Files cleared."),
                html.Div("Files cleared."),
            )
        return no_update, no_update

    # ------- PLOT CALLBACK

    DF_TO_PLOT = {}

    # Callback to display information about selected files
    @callback(
        Output("plot-display", "children", allow_duplicate=True),
        Input("files-multiselect", "value"),
        State("uploaded-files-storage", "children"),
        prevent_initial_call=True,
    )
    def display_plots(selected_files, stored_data):
        if not selected_files or not stored_data:
            return html.Div("No files selected.")

        file_data = json.loads(stored_data)
        plot_div = []
        combined_df = []
        for item in file_data:
            if item["filename"] in selected_files:
                combined_df.append(dataframes.get(item["filename"]))
                mdscols = item["dimensions"]
                MIN_TREENUM = item["MIN_TREENUM"]
                MAX_TREENUM = item["MAX_TREENUM"]

        combined_df = pd.concat(combined_df)
        if len(selected_files) > 1:
            combined_df["group"] = combined_df["file"] + "/" + combined_df["group"]

        default_fig = make_plot_grid()
        x, y, z = mdscols[0], mdscols[1], mdscols[2]
        DF_TO_PLOT["df"] = combined_df
        DF_TO_PLOT["GROUPS"] = combined_df["group"].unique()
        DF_TO_PLOT["GROUP_COLORS"] = px.colors.qualitative.Dark24[
            : len(DF_TO_PLOT["GROUPS"])
        ]
        DF_TO_PLOT["COLOR_DICT"] = {
            g: c for g, c in zip(DF_TO_PLOT["GROUPS"], DF_TO_PLOT["GROUP_COLORS"])
        }

        add_trace_multiplot(
            default_fig,
            DF_TO_PLOT["df"],
            x,
            y,
            z,
            DF_TO_PLOT["GROUPS"],
            DF_TO_PLOT["COLOR_DICT"],
        )

        # Controls row with slider and checkbox
        controls = html.Div(
            [
                html.Div(
                    [
                        html.Label(
                            "Dimensions:",
                            style={"display": "block", "margin-bottom": "2px"},
                        ),
                        dcc.Checklist(
                            options=mdscols,
                            value=mdscols[:3],
                            id="dimensions-box",
                            inline=True,
                        ),
                    ],
                    style={"width": "25%", "padding": "5px"},
                ),
                # tree num slider
                html.Div(
                    [
                        html.Label("Filter by Tree Number Range:"),
                        dcc.RangeSlider(
                            id="treenum-slider",
                            min=MIN_TREENUM,
                            max=MAX_TREENUM,
                            value=[MIN_TREENUM, MAX_TREENUM],
                            marks={
                                MIN_TREENUM: str(MIN_TREENUM),
                                MAX_TREENUM: str(MAX_TREENUM),
                            },
                            step=1,
                        ),
                    ],
                    style={"width": "75%", "padding": "5px"},
                ),
            ],
            style={"display": "flex", "align-items": "center", "padding": "5px 0"},
        )

        plot_div.append(controls)
        plot_div.append(
            html.Div(
                # 3D plot
                dcc.Graph(figure=default_fig, id="graph", style={"height": "75vh"}),
                style={
                    "width": "95%",
                    "display": "inline-block",
                    "vertical-align": "top",
                },
            )
        )

        return html.Div(plot_div)

    # Add controls to build the interaction
    @callback(
        Output(component_id="graph", component_property="figure", allow_duplicate=True),
        [
            Input(component_id="dimensions-box", component_property="value"),
            Input(component_id="treenum-slider", component_property="value"),
        ],
        [Input(component_id="graph", component_property="figure")],
        prevent_initial_call=True,
    )
    def update_graph(mds_selected, treenum_range, current_figure):
        # Only update the graph if exactly 3 options are selected
        if len(mds_selected) != 3:
            return current_figure

        # Filter data based on treenum range
        df = DF_TO_PLOT["df"]
        filtered_dff = df[
            (df["treenum"] >= treenum_range[0]) & (df["treenum"] <= treenum_range[1])
        ]

        x, y, z = mds_selected

        fig = make_plot_grid()
        add_trace_multiplot(
            fig, filtered_dff, x, y, z, DF_TO_PLOT["GROUPS"], DF_TO_PLOT["COLOR_DICT"]
        )

        # If we have a current figure, try to preserve visibility settings
        if (
            current_figure
            and "data" in current_figure
            and len(current_figure["data"]) == len(fig.data)
        ):
            for i in range(len(fig.data)):
                if "visible" in current_figure["data"][i]:
                    fig.data[i].visible = current_figure["data"][i]["visible"]

        return fig
