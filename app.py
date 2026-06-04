from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

import config
from logic.data_cleaner import clean_sales_file
from logic.data_loader import UploadError, preview_excel, save_upload
from logic.formatters import format_naira_compact, format_naira_full
from logic.forecasting_engine import forecast_sales_file
from logic.profit_analyser import analyse_profit_file
from logic.recommendation_engine import generate_stock_advice_file
from logic.sales_analyser import analyse_sales_file

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["UPLOAD_FOLDER"] = str(config.UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

config.ensure_directories()


app.jinja_env.filters["naira_compact"] = format_naira_compact
app.jinja_env.filters["naira_full"] = format_naira_full


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    preview = session.get("upload_preview")
    cleaning_report = session.get("cleaning_report")

    if request.method == "POST":
        uploaded_file = request.files.get("file")

        try:
            filepath = save_upload(
                uploaded_file,
                config.UPLOAD_FOLDER,
                config.ALLOWED_EXTENSIONS,
            )
            preview = preview_excel(filepath)

            if preview.get("success"):
                cleaning_report = clean_sales_file(filepath, config.DATA_FOLDER)

                if cleaning_report.get("success"):
                    flash("File uploaded and cleaned successfully.", "success")
                    session["upload_preview"] = preview
                    cleaning_report.pop("cleaned_path", None)
                    session["cleaning_report"] = cleaning_report
                else:
                    flash(
                        cleaning_report.get("error", "Could not clean the uploaded file."),
                        "error",
                    )
                    session["upload_preview"] = preview
                    session.pop("cleaning_report", None)
            else:
                flash(preview.get("error", "Could not preview the uploaded file."), "error")
                session.pop("upload_preview", None)
                session.pop("cleaning_report", None)

        except UploadError as exc:
            flash(str(exc), "error")
            session.pop("upload_preview", None)
            session.pop("cleaning_report", None)

        return redirect(url_for("upload"))

    return render_template(
        "upload.html",
        preview=preview,
        cleaning_report=cleaning_report,
    )


def _cleaned_data_path() -> Path | None:
    cleaning_report = session.get("cleaning_report") or {}
    cleaned_filename = cleaning_report.get("cleaned_filename")
    if not cleaned_filename:
        return None
    return config.DATA_FOLDER / cleaned_filename


@app.route("/dashboard")
def dashboard():
    cleaned_path = _cleaned_data_path()
    if cleaned_path is None:
        flash("Upload and clean a product data file before opening the sales dashboard.", "error")
        return redirect(url_for("upload"))

    analysis = analyse_sales_file(cleaned_path)
    if not analysis.get("success"):
        flash(analysis.get("error", "Could not analyse the cleaned sales data."), "error")
        return redirect(url_for("upload"))

    chart_data = json.dumps(analysis.get("charts", {}))
    return render_template(
        "dashboard.html",
        analysis=analysis,
        chart_data=chart_data,
    )


@app.route("/forecast")
def forecast():
    cleaned_path = _cleaned_data_path()
    if cleaned_path is None:
        flash("Upload and clean a product data file before opening the forecast.", "error")
        return redirect(url_for("upload"))

    period = request.args.get("period", 1, type=int)
    if period not in (1, 3, 6):
        period = 1

    product = request.args.get("product", "").strip() or None

    forecast_report = forecast_sales_file(
        cleaned_path,
        forecast_periods=period,
        product=product,
    )
    if not forecast_report.get("success"):
        flash(forecast_report.get("error", "Could not forecast from the cleaned sales data."), "error")
        return redirect(url_for("upload"))

    chart_data = json.dumps(forecast_report.get("charts", {}))
    return render_template(
        "forecast.html",
        forecast=forecast_report,
        chart_data=chart_data,
    )


@app.route("/profit-loss")
def profit_loss():
    cleaned_path = _cleaned_data_path()
    if cleaned_path is None:
        flash("Upload and clean a product data file before opening profit & loss.", "error")
        return redirect(url_for("upload"))

    analysis = analyse_profit_file(cleaned_path)
    if not analysis.get("success"):
        flash(analysis.get("error", "Could not analyse profit from the cleaned sales data."), "error")
        return redirect(url_for("upload"))

    chart_data = json.dumps(analysis.get("charts", {}))
    return render_template(
        "profit_loss.html",
        analysis=analysis,
        chart_data=chart_data,
    )


@app.route("/stock-advice")
def stock_advice():
    cleaned_path = _cleaned_data_path()
    if cleaned_path is None:
        flash("Upload and clean a product data file before opening stock advice.", "error")
        return redirect(url_for("upload"))

    advice = generate_stock_advice_file(cleaned_path)
    if not advice.get("success"):
        flash(advice.get("error", "Could not generate stock advice from the cleaned sales data."), "error")
        return redirect(url_for("upload"))

    chart_data = json.dumps(advice.get("charts", {}))
    return render_template(
        "stock_advice.html",
        advice=advice,
        chart_data=chart_data,
    )


if __name__ == "__main__":
    app.run(debug=True)
