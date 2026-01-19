document.addEventListener("DOMContentLoaded", () => {
    const table = document.getElementById("resources-table");
    const addBtn = document.getElementById("add-resource-btn");

    addBtn.addEventListener("click", async () => {
        const kind = prompt("Тип ресурса: openai | telegram | web");
        if (!kind) return;

        const r = await fetch("/ui/resources", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind }),
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
        if (!tr) return;

        const id = tr.dataset.id;

        if (e.target.classList.contains("delete-cell")) {
            e.stopPropagation();

            if (!confirm("Удалить ресурс полностью?")) return;

            const r = await fetch(`/ui/resources/${id}`, {
                method: "DELETE",
            });

            if (r.ok) {
                tr.remove();
            } else {
                alert("Ошибка удаления");
            }
            return;
        }

        window.location.href = `/ui/resources/${id}`;
    });
});
