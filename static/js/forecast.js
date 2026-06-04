(function () {
    const dataElement = document.getElementById("forecast-data");
    if (!dataElement) {
        return;
    }

    const charts = JSON.parse(dataElement.textContent || "{}");

    function formatNairaCompact(value) {
        const amount = Number(value);
        if (Number.isNaN(amount)) {
            return "₦0";
        }
        const abs = Math.abs(amount);
        if (abs >= 1_000_000) {
            const millions = amount / 1_000_000;
            const rounded = millions % 1 === 0 ? millions.toFixed(0) : millions.toFixed(1);
            return `₦${rounded}M`;
        }
        if (abs >= 1_000) {
            const thousands = amount / 1_000;
            const rounded = thousands % 1 === 0 ? thousands.toFixed(0) : thousands.toFixed(1);
            return `₦${rounded}K`;
        }
        return `₦${Math.round(amount).toLocaleString()}`;
    }

    function formatNairaFull(value) {
        const amount = Number(value);
        if (Number.isNaN(amount)) {
            return "N/A";
        }
        return `₦${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    function buildMoneyAxis(values, title) {
        const clean = values.filter((value) => value != null && !Number.isNaN(value));
        const max = clean.length ? Math.max(...clean) : 0;

        if (max <= 0) {
            return {
                title,
                tickvals: [0],
                ticktext: ["₦0"],
            };
        }

        const tickCount = 5;
        const rawStep = max / (tickCount - 1);
        const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
        const step = Math.max(magnitude, Math.ceil(rawStep / magnitude) * magnitude);
        const tickvals = [];
        const ticktext = [];

        for (let value = 0; value <= max + step * 0.01; value += step) {
            tickvals.push(value);
            ticktext.push(formatNairaCompact(value));
            if (tickvals.length >= tickCount) {
                break;
            }
        }

        return {
            title,
            tickvals,
            ticktext,
            automargin: true,
        };
    }

    function baseLayout(extra) {
        return {
            height: 280,
            margin: { t: 12, r: 12, b: 48, l: 52 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Arial, sans-serif", color: "#000000", size: 12 },
            ...extra,
        };
    }

    const plotConfig = { responsive: true, displayModeBar: false };

    function buildJourneyHoverText(point, productName) {
        const lines = [`Month: ${point.month}`, `Product: ${productName}`];
        if (point.is_forecast) {
            lines.push(`Expected units sold: ${point.units}`);
        } else {
            lines.push(`Actual units sold: ${point.units}`);
        }
        if (point.money != null) {
            const moneyLabel = point.is_forecast ? "Expected revenue" : "Revenue";
            lines.push(`${moneyLabel}: ${formatNairaFull(point.money)}`);
        }
        if (point.profit != null) {
            const profitLabel = point.is_forecast ? "Expected profit" : "Profit";
            lines.push(`${profitLabel}: ${formatNairaFull(point.profit)}`);
        }
        lines.push(`Trend status: ${point.trend_status}`);
        lines.push(`Restock advice: ${point.restock_advice}`);
        if (point.marker_label) {
            lines.push(`Marker: ${point.marker_label}`);
        }
        return lines.join("<br>");
    }

    function plotProductJourney(journey) {
        const elementId = "forecast-journey-chart";
        const element = document.getElementById(elementId);
        if (!element || !journey || !journey.points || !journey.points.length) {
            return;
        }

        const productName = journey.product;
        const points = journey.points;
        const historyPoints = points.filter((point) => !point.is_forecast);
        const forecastPoints = points.filter((point) => point.is_forecast);
        const lastHistory = historyPoints[historyPoints.length - 1];

        const historyX = historyPoints.map((point) => point.month);
        const historyY = historyPoints.map((point) => point.units);
        const forecastX = [lastHistory.month].concat(forecastPoints.map((point) => point.month));
        const forecastY = [lastHistory.units].concat(forecastPoints.map((point) => point.units));

        const markerPoints = points.filter((point) => point.marker);
        const markerColors = {
            peak: "#000000",
            lowest: "#393d46",
            now: "#ffdd00",
            forecast_start: "#ffdd00",
            restock: "#000000",
            forecast_start_restock: "#ffdd00",
        };

        const traces = [
            {
                x: historyX,
                y: historyY,
                type: "scatter",
                mode: "lines+markers",
                name: "Past sales",
                line: { color: "#000000", width: 3, shape: "spline" },
                marker: { color: "#000000", size: 8, line: { color: "#ffffff", width: 1.5 } },
                hovertext: historyPoints.map((point) => buildJourneyHoverText(point, productName)),
                hoverinfo: "text",
            },
            {
                x: forecastX,
                y: forecastY,
                type: "scatter",
                mode: "lines+markers",
                name: "Forecast",
                line: { color: "#ffdd00", width: 3, dash: "dash", shape: "spline" },
                marker: { color: "#ffdd00", size: 9, line: { color: "#000000", width: 1.5 } },
                hovertext: [lastHistory]
                    .concat(forecastPoints)
                    .map((point) => buildJourneyHoverText(point, productName)),
                hoverinfo: "text",
            },
        ];

        if (markerPoints.length) {
            traces.push({
                x: markerPoints.map((point) => point.month),
                y: markerPoints.map((point) => point.units),
                type: "scatter",
                mode: "markers+text",
                name: "Markers",
                text: markerPoints.map((point) => point.marker_label || ""),
                textposition: "top center",
                textfont: { size: 11, color: "#000000" },
                hovertext: markerPoints.map((point) =>
                    buildJourneyHoverText(point, productName)
                ),
                hoverinfo: "text",
                marker: {
                    size: 14,
                    color: markerPoints.map(
                        (point) => markerColors[point.marker] || "#000000"
                    ),
                    line: { color: "#ffffff", width: 2 },
                    symbol: "diamond",
                },
                showlegend: false,
            });
        }

        const shapes = [];
        if (journey.forecast_start_month) {
            shapes.push({
                type: "line",
                x0: journey.forecast_start_month,
                x1: journey.forecast_start_month,
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: "rgba(57, 61, 70, 0.35)", width: 2, dash: "dot" },
            });
        }

        const allUnits = points.map((point) => point.units);
        const yMax = Math.max(...allUnits, 1);

        Plotly.newPlot(
            elementId,
            traces,
            baseLayout({
                height: 420,
                margin: { t: 28, r: 20, b: 56, l: 56 },
                xaxis: {
                    title: "Month",
                    automargin: true,
                    showgrid: true,
                    gridcolor: "rgba(0,0,0,0.06)",
                },
                yaxis: {
                    title: "Units sold",
                    automargin: true,
                    rangemode: "tozero",
                    range: [0, yMax * 1.18],
                    showgrid: true,
                    gridcolor: "rgba(0,0,0,0.06)",
                },
                shapes,
                legend: {
                    orientation: "h",
                    y: 1.08,
                    x: 0,
                    xanchor: "left",
                },
                hovermode: "closest",
            }),
            plotConfig
        );
    }

    function plotHistoryAndForecast(elementId, series, yTitle, isMoney) {
        const allLabels = series.history_labels.concat(series.forecast_labels);
        const historyY = series.history_values.concat(
            Array(series.forecast_labels.length).fill(null)
        );
        const forecastY = Array(series.history_labels.length)
            .fill(null)
            .concat(series.forecast_values);

        const yaxis = isMoney
            ? buildMoneyAxis(series.history_values.concat(series.forecast_values), yTitle)
            : { title: yTitle, automargin: true, rangemode: "tozero" };

        Plotly.newPlot(
            elementId,
            [
                {
                    x: allLabels,
                    y: historyY,
                    type: "bar",
                    name: "Past",
                    marker: { color: "#000000" },
                    hovertemplate: `Month: %{x}<br>${yTitle}: %{y}<extra></extra>`,
                },
                {
                    x: allLabels,
                    y: forecastY,
                    type: "bar",
                    name: "Expected",
                    marker: { color: "#ffdd00" },
                    hovertemplate: `Month: %{x}<br>${yTitle}: %{y}<extra></extra>`,
                },
            ],
            baseLayout({
                xaxis: { title: "Month", automargin: true },
                yaxis,
                barmode: "overlay",
                margin: { t: 12, r: 12, b: 48, l: 52 },
                legend: { orientation: "h", y: 1.02, x: 0.5, xanchor: "center" },
            }),
            plotConfig
        );
    }

    function plotHorizontalProducts(elementId, series, xTitle, isMoney) {
        if (!series || !series.labels || !series.labels.length) {
            return;
        }

        Plotly.newPlot(
            elementId,
            [
                {
                    x: series.values,
                    y: series.labels,
                    type: "bar",
                    orientation: "h",
                    marker: { color: "#ffdd00" },
                    hovertemplate: isMoney
                        ? "Product: %{y}<br>Value: %{customdata}<extra></extra>"
                        : "Product: %{y}<br>Units: %{x}<extra></extra>",
                    customdata: isMoney
                        ? series.values.map((value) => formatNairaCompact(value))
                        : undefined,
                },
            ],
            baseLayout({
                margin: { t: 12, r: 12, b: 48, l: 132 },
                xaxis: isMoney
                    ? { ...buildMoneyAxis(series.values, xTitle), rangemode: "tozero" }
                    : { title: xTitle, automargin: true, rangemode: "tozero" },
                yaxis: { title: "Product", automargin: true, categoryorder: "total ascending" },
                showlegend: false,
            }),
            plotConfig
        );
    }

    if (charts.journey_line) {
        plotProductJourney(charts.journey_line);
        return;
    }

    if (charts.products_sold) {
        plotHistoryAndForecast(
            "forecast-products-chart",
            charts.products_sold,
            "Products sold",
            false
        );
    }

    if (charts.money_made) {
        plotHistoryAndForecast(
            "forecast-money-chart",
            charts.money_made,
            "Money made",
            true
        );
    }

    if (charts.profit) {
        plotHistoryAndForecast(
            "forecast-profit-chart",
            charts.profit,
            "Profit",
            true
        );
    }

    if (charts.product_units) {
        plotHorizontalProducts(
            "forecast-product-units-chart",
            charts.product_units,
            "Expected sold",
            false
        );
    }

    if (charts.product_money) {
        plotHorizontalProducts(
            "forecast-product-money-chart",
            charts.product_money,
            "Expected money made",
            true
        );
    }

    if (charts.product_profit) {
        plotHorizontalProducts(
            "forecast-product-profit-chart",
            charts.product_profit,
            "Expected profit",
            true
        );
    }
})();
