function initRouteChart() {
  const canvas = document.getElementById("routeChart");
  if (!canvas || !window.Chart) return;
  const data = JSON.parse(canvas.dataset.routes || "{}");
  new Chart(canvas, {
    type: "bar",
    data: {
      labels: Object.keys(data),
      datasets: [{ label: "Route được chọn", data: Object.values(data), backgroundColor: "#2563eb" }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });
}
document.addEventListener("DOMContentLoaded", initRouteChart);
