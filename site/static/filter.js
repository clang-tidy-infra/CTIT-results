(() => {
  const input = document.getElementById("filter");
  const apply = () => {
    const query = input.value.trim().toLowerCase();
    for (const group of document.querySelectorAll(".group")) {
      group.hidden = query !== "" && !group.dataset.key.includes(query);
    }
  };
  input.value = new URLSearchParams(location.search).get("q") || "";
  input.addEventListener("input", apply);
  apply();
})();
