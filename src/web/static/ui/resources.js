document.addEventListener("DOMContentLoaded", () => {
    const tbody = document.querySelector("#resources-table tbody");
    const btn = document.getElementById("add-resource-btn");

    btn.addEventListener("click", () => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>—</td>
            <td><input placeholder="kind"></td>
            <td><input placeholder="code"></td>
            <td><input placeholder="title"></td>
            <td>true</td>
        `;
        tbody.prepend(tr);
    });
});
