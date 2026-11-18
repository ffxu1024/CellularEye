"use strict";

const search = document.querySelector("#collection-search");
if (search) {
  const keys = ["target", "weather", "trajectory", "direction"];
  const controls = Object.fromEntries(keys.map((key) => [key, document.querySelector(`#collection-${key}`)]));
  const rows = [...document.querySelectorAll(".catalog-table tbody tr")];
  const count = document.querySelector("#collection-count");
  const empty = document.querySelector("#collection-empty");
  function apply() {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const match = row.dataset.search.includes(query) && keys.every((key) => !controls[key].value || row.dataset[key] === controls[key].value);
      row.hidden = !match;
      if (match) visible += 1;
    });
    count.textContent = `Showing ${visible} of ${rows.length} collections`;
    empty.hidden = visible !== 0;
  }
  const params = new URLSearchParams(window.location.search);
  keys.forEach((key) => {
    const value = params.get(key);
    if ([...controls[key].options].some((option) => option.value === value)) controls[key].value = value;
    controls[key].addEventListener("change", apply);
  });
  search.addEventListener("input", apply);
  document.querySelector("#collection-reset").addEventListener("click", () => {
    search.value = "";
    keys.forEach((key) => { controls[key].value = ""; });
    apply();
  });
  apply();
}
