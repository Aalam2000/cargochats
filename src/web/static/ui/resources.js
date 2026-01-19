document.addEventListener("DOMContentLoaded", () => {
    const addBtn = document.getElementById("add-resource-btn");
    const createRow = document.getElementById("create-row");
    const createBtn = document.getElementById("create-confirm");
    const table = document.getElementById("resources-table");

    addBtn.addEventListener("click", () => {
        createRow.style.display = "";
    });

    createBtn.addEventListener("click", async () => {
        const kind = document.getElementById("new-kind").value;
        const title = document.getElementById("new-title").value.trim();

        if (!kind || !title) {
            alert("Выбери тип и задай название");
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
        window.location.href = `/ui/resources/${data.id}`;
    });

    table.addEventListener("click", async (e) => {
        const tr = e.target.closest("tr");
        if (!tr || !tr.dataset.id) return;

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
