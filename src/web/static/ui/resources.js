document.addEventListener("DOMContentLoaded", () => {
    const tbody = document.querySelector("#resources-table tbody");

    const mockResources = [
        { id: "-", type: "telegram", title: "Telegram Chat", status: "inactive" },
        { id: "-", type: "tilda", title: "Tilda Widget", status: "inactive" }
    ];

    mockResources.forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${r.id}</td>
            <td>${r.type}</td>
            <td>${r.title}</td>
            <td>${r.status}</td>
        `;
        tbody.appendChild(tr);
    });
});
