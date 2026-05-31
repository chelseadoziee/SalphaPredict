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
