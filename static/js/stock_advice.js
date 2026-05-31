(function () {
    const dataElement = document.getElementById("stock-advice-data");
    if (!dataElement) {
        return;
    }

    const charts = JSON.parse(dataElement.textContent || "{}");

    function baseLayout(extra) {
        return {
            height: 280,
            margin: { t: 12, r: 12, b: 48, l: 132 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Arial, sans-serif", color: "#000000", size: 12 },
            ...extra,
        };
    }

    const plotConfig = { responsive: true, displayModeBar: false };

    if (charts.suggested_stock) {
        const stock = charts.suggested_stock;

        Plotly.newPlot(
            "suggested-stock-chart",
            [
                {
                    x: stock.values,
                    y: stock.labels,
                    type: "bar",
                    orientation: "h",
                    marker: { color: "#ffdd00" },
                    hovertemplate: "Product: %{y}<br>Suggested stock: %{x}<extra></extra>",
                },
            ],
            baseLayout({
                xaxis: { title: "Suggested units", automargin: true, rangemode: "tozero" },
                yaxis: { title: "Product", automargin: true, categoryorder: "total ascending" },
                showlegend: false,
            }),
            plotConfig
        );
    }
})();
