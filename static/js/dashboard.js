(function () {
    const dataElement = document.getElementById("dashboard-data");
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

    function buildMoneyAxis(values) {
        const clean = values.filter((value) => value != null && !Number.isNaN(value));
        const max = clean.length ? Math.max(...clean) : 0;

        if (max <= 0) {
            return {
                title: "Money made",
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
            title: "Money made",
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

    if (charts.monthly_trend) {
        const monthly = charts.monthly_trend;

        Plotly.newPlot(
            "monthly-products-chart",
            [
                {
                    x: monthly.labels,
                    y: monthly.quantity,
                    type: "bar",
                    name: "Products sold",
                    marker: { color: "#ffdd00" },
                    hovertemplate: "Month: %{x}<br>Products sold: %{y}<extra></extra>",
                },
            ],
            baseLayout({
                xaxis: { title: "Month", automargin: true },
                yaxis: { title: "Products sold", automargin: true, rangemode: "tozero" },
                showlegend: false,
            }),
            plotConfig
        );

        if (monthly.revenue && monthly.revenue.some((value) => value !== null)) {
            Plotly.newPlot(
                "monthly-money-chart",
                [
                    {
                        x: monthly.labels,
                        y: monthly.revenue,
                        type: "bar",
                        name: "Money made",
                        marker: { color: "#000000" },
                        hovertemplate:
                            "Month: %{x}<br>Money made: %{customdata}<extra></extra>",
                        customdata: monthly.revenue.map((value) => formatNairaCompact(value)),
                    },
                ],
                baseLayout({
                    xaxis: { title: "Month", automargin: true },
                    yaxis: {
                        ...buildMoneyAxis(monthly.revenue),
                        rangemode: "tozero",
                    },
                    showlegend: false,
                }),
                plotConfig
            );
        }
    }

    if (charts.top_products) {
        Plotly.newPlot(
            "top-products-chart",
            [
                {
                    x: charts.top_products.quantity,
                    y: charts.top_products.labels,
                    type: "bar",
                    orientation: "h",
                    marker: { color: "#000000" },
                    hovertemplate: "Product: %{y}<br>Products sold: %{x}<extra></extra>",
                },
            ],
            baseLayout({
                margin: { t: 12, r: 12, b: 48, l: 120 },
                xaxis: { title: "Products sold", automargin: true, rangemode: "tozero" },
                yaxis: { title: "Product", automargin: true, categoryorder: "total ascending" },
                showlegend: false,
            }),
            plotConfig
        );
    }

    if (charts.revenue_by_product) {
        const revenueValues = charts.revenue_by_product.revenue;

        Plotly.newPlot(
            "revenue-by-product-chart",
            [
                {
                    x: revenueValues,
                    y: charts.revenue_by_product.labels,
                    type: "bar",
                    orientation: "h",
                    marker: { color: "#ffdd00" },
                    hovertemplate: "Product: %{y}<br>Money made: %{customdata}<extra></extra>",
                    customdata: revenueValues.map((value) => formatNairaCompact(value)),
                },
            ],
            baseLayout({
                margin: { t: 12, r: 12, b: 48, l: 132 },
                xaxis: {
                    ...buildMoneyAxis(revenueValues),
                    rangemode: "tozero",
                },
                yaxis: { title: "Product", automargin: true, categoryorder: "total ascending" },
                showlegend: false,
            }),
            plotConfig
        );
    }

    if (charts.regions) {
        Plotly.newPlot(
            "regions-chart",
            [
                {
                    labels: charts.regions.labels,
                    values: charts.regions.quantity,
                    type: "pie",
                    hole: 0.35,
                    marker: {
                        colors: ["#ffdd00", "#000000", "#393d46", "#f0ece9", "#ffe94d"],
                    },
                    hovertemplate: "Area: %{label}<br>Products sold: %{value}<extra></extra>",
                },
            ],
            baseLayout({
                showlegend: true,
                margin: { t: 12, r: 12, b: 48, l: 52 },
                legend: { orientation: "h", y: 1.02, x: 0.5, xanchor: "center" },
            }),
            plotConfig
        );
    }
})();
