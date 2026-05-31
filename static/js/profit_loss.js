(function () {
    const dataElement = document.getElementById("profit-loss-data");
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

    if (charts.monthly_profit_and_loss) {
        const monthly = charts.monthly_profit_and_loss;
        const axisValues = monthly.gross_profit.concat(monthly.loss);

        Plotly.newPlot(
            "monthly-profit-loss-chart",
            [
                {
                    x: monthly.labels,
                    y: monthly.gross_profit,
                    type: "bar",
                    name: "Gross profit",
                    marker: { color: "#ffdd00" },
                    hovertemplate:
                        "Month: %{x}<br>Gross profit: %{customdata}<extra></extra>",
                    customdata: monthly.gross_profit.map((value) => formatNairaCompact(value)),
                },
                {
                    x: monthly.labels,
                    y: monthly.loss,
                    type: "bar",
                    name: "Loss",
                    marker: { color: "#000000" },
                    hovertemplate: "Month: %{x}<br>Loss: %{customdata}<extra></extra>",
                    customdata: monthly.loss.map((value) => formatNairaCompact(value)),
                },
            ],
            baseLayout({
                xaxis: { title: "Month", automargin: true },
                yaxis: {
                    ...buildMoneyAxis(axisValues, "Amount"),
                    rangemode: "tozero",
                },
                barmode: "group",
                margin: { t: 12, r: 12, b: 48, l: 52 },
                legend: { orientation: "h", y: 1.02, x: 0.5, xanchor: "center" },
            }),
            plotConfig
        );
    }

    if (charts.monthly_money_and_cost) {
        const monthly = charts.monthly_money_and_cost;
        const axisValues = monthly.money_made.concat(monthly.total_cost);

        Plotly.newPlot(
            "monthly-money-cost-chart",
            [
                {
                    x: monthly.labels,
                    y: monthly.money_made,
                    type: "bar",
                    name: "Money made",
                    marker: { color: "#000000" },
                    hovertemplate:
                        "Month: %{x}<br>Money made: %{customdata}<extra></extra>",
                    customdata: monthly.money_made.map((value) => formatNairaCompact(value)),
                },
                {
                    x: monthly.labels,
                    y: monthly.total_cost,
                    type: "bar",
                    name: "Total cost",
                    marker: { color: "#393d46" },
                    hovertemplate:
                        "Month: %{x}<br>Total cost: %{customdata}<extra></extra>",
                    customdata: monthly.total_cost.map((value) => formatNairaCompact(value)),
                },
            ],
            baseLayout({
                xaxis: { title: "Month", automargin: true },
                yaxis: {
                    ...buildMoneyAxis(axisValues, "Amount"),
                    rangemode: "tozero",
                },
                barmode: "group",
                margin: { t: 12, r: 12, b: 48, l: 52 },
                legend: { orientation: "h", y: 1.02, x: 0.5, xanchor: "center" },
            }),
            plotConfig
        );
    }

    if (charts.profit_by_product && charts.profit_by_product.labels.length) {
        const products = charts.profit_by_product;

        Plotly.newPlot(
            "profit-by-product-chart",
            [
                {
                    x: products.profit,
                    y: products.labels,
                    type: "bar",
                    orientation: "h",
                    marker: { color: "#ffdd00" },
                    hovertemplate: "Product: %{y}<br>Gross profit: %{customdata}<extra></extra>",
                    customdata: products.profit.map((value) => formatNairaCompact(value)),
                },
            ],
            baseLayout({
                margin: { t: 12, r: 12, b: 48, l: 132 },
                xaxis: {
                    ...buildMoneyAxis(products.profit, "Gross profit"),
                    rangemode: "tozero",
                },
                yaxis: { title: "Product", automargin: true, categoryorder: "total ascending" },
                showlegend: false,
            }),
            plotConfig
        );
    }

    if (charts.loss_by_product) {
        const products = charts.loss_by_product;

        Plotly.newPlot(
            "loss-by-product-chart",
            [
                {
                    x: products.loss,
                    y: products.labels,
                    type: "bar",
                    orientation: "h",
                    marker: { color: "#000000" },
                    hovertemplate: "Product: %{y}<br>Loss: %{customdata}<extra></extra>",
                    customdata: products.loss.map((value) => formatNairaCompact(value)),
                },
            ],
            baseLayout({
                margin: { t: 12, r: 12, b: 48, l: 132 },
                xaxis: {
                    ...buildMoneyAxis(products.loss, "Loss"),
                    rangemode: "tozero",
                },
                yaxis: { title: "Product", automargin: true, categoryorder: "total ascending" },
                showlegend: false,
            }),
            plotConfig
        );
    }
})();
