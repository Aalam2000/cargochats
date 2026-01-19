document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("create-modal");
    const openBtn = document.getElementById("open-create-modal");
    const cancelBtn = document.getElementById("modal-cancel");
    const createBtn = document.getElementById("modal-create");

    const kindInput = document.getElementById("modal-kind");
    const titleInput = document.getElementById("modal-title");
    const tableBody = document.querySelector("#resources-table tbody");

    openBtn.onclick = () => {
        modal.classList.remove("hidden");
    };

    cancelBtn.onclick = () => {
        modal.classList.add("hidden");
        kindInput.value = "";
        titleInput.value = "";
    };

    createBtn.onclick = async () => {
        const kind = kindInput.value;
        const title = titleInput.value.trim();

        if (!kind || !title) {
            alert("Заполни тип и название");
            return;
        }

        const r = await fetch("/ui/resources", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind, title }),
        });

        if (!r.ok) {
            alert("Ошибка создания ресурса");
            return;
        }

        const data = await r.json();

        const tr = document.createElement("tr");
        tr.dataset.id = data.id;
        tr.className = "resource-row";
        tr.innerHTML = `
            <td>${data.id}</td>
            <td>${kind}</td>
            <td>${title}</td>
            <td>true</td>
            <td class="delete-cell">🗑</td>
        `;
        tableBody.appendChild(tr);

        modal.classList.add("hidden");
        kindInput.value = "";
        titleInput.value = "";
    };

    tableBody.addEventListener("click", async (e) => {
        const tr = e.target.closest("tr");
        if (!tr) return;

        const id = tr.dataset.id;

        if (e.target.classList.contains("delete-cell")) {
            e.stopPropagation();
            if (!confirm("Удалить ресурс?")) return;

            const r = await fetch(`/ui/resources/${id}`, { method: "DELETE" });
            if (r.ok) tr.remove();
            return;
        }

        window.location.href = `/ui/resources/${id}`;
    });
});
