const UNITS = [
    "piece",
    "g",
    "kg",
    "ml",
    "l",
    "pack",
    "bottle",
    "jar",
    "can",
    "unknown"
];


const UNIT_LABELS = {
    piece: "pièce",
    g: "g",
    kg: "kg",
    ml: "ml",
    l: "l",
    pack: "paquet",
    bottle: "bouteille",
    jar: "bocal",
    can: "boîte",
    unknown: "inconnue"
};


const CATEGORIES = [
    "vegetable",
    "fruit",
    "meat",
    "fish",
    "dairy",
    "egg",
    "drink",
    "condiment",
    "prepared_food",
    "other"
];


const CATEGORY_LABELS = {
    vegetable: "Légumes",
    fruit: "Fruits",
    meat: "Viandes",
    fish: "Poissons",
    dairy: "Produits laitiers",
    egg: "Œufs",
    drink: "Boissons",
    condiment: "Condiments",
    prepared_food: "Plats préparés",
    other: "Autres"
};


let currentScanId = null;
let detectedItems = [];


const form =
    document.getElementById("scan-form");

const imageInput =
    document.getElementById("images");

const scanButton =
    document.getElementById("scan-button");

const scanStatus =
    document.getElementById("scan-status");

const analysisSection =
    document.getElementById("analysis");

const itemsContainer =
    document.getElementById("items");

const warningsContainer =
    document.getElementById("warnings");

const confirmButton =
    document.getElementById("confirm");

const photoPreview =
    document.getElementById("photo-preview");


function escapeHtml(value) {
    const div = document.createElement("div");

    div.textContent = value ?? "";

    return div.innerHTML;
}


async function fetchJson(url, options = {}) {
    const response = await fetch(
        url,
        options
    );

    if (!response.ok) {
        const message = await response.text();

        throw new Error(
            message || `HTTP ${response.status}`
        );
    }

    return response.json();
}


function formatQuantity(
    quantity,
    unit
) {
    if (
        quantity === null ||
        quantity === undefined ||
        unit === "unknown"
    ) {
        return "Quantité inconnue";
    }

    const label =
        UNIT_LABELS[unit] ?? unit;

    return `${quantity} ${label}`;
}


function setScanStatus(
    message,
    type = "info"
) {
    scanStatus.textContent = message;
    scanStatus.className =
        `scan-status ${type}`;
    scanStatus.hidden = false;
}


function clearScanStatus() {
    scanStatus.hidden = true;
    scanStatus.textContent = "";
}


async function loadInventory() {
    const groupsContainer =
        document.getElementById(
            "inventory-groups"
        );

    const empty =
        document.getElementById(
            "inventory-empty"
        );

    const errorElement =
        document.getElementById(
            "fridge-error"
        );

    try {
        const response =
            await fetchJson(
                "/api/inventory"
            );

        const inventory =
            response.items;

        document.getElementById(
            "inventory-count"
        ).textContent =
            inventory.length;

        groupsContainer.innerHTML = "";

        if (inventory.length === 0) {
            empty.hidden = false;

            document.getElementById(
                "inventory-summary"
            ).textContent =
                "Aucun inventaire enregistré.";

            return;
        }

        empty.hidden = true;

        const timestamps =
            inventory
                .map(item =>
                    Date.parse(
                        item.updated_at
                    )
                )
                .filter(value =>
                    Number.isFinite(value)
                );

        if (timestamps.length > 0) {
            const newest =
                new Date(
                    Math.max(...timestamps)
                );

            document.getElementById(
                "inventory-summary"
            ).textContent =
                "Mis à jour le " +
                newest.toLocaleString(
                    "fr-FR",
                    {
                        dateStyle: "medium",
                        timeStyle: "short"
                    }
                );
        } else {
            document.getElementById(
                "inventory-summary"
            ).textContent =
                `${inventory.length} produits`;
        }

        const groups = {};

        for (const item of inventory) {
            const category =
                item.category || "other";

            if (!groups[category]) {
                groups[category] = [];
            }

            groups[category].push(
                item
            );
        }

        for (const category of CATEGORIES) {
            const items =
                groups[category];

            if (!items?.length) {
                continue;
            }

            const section =
                document.createElement(
                    "section"
                );

            section.className =
                "inventory-group";

            const title =
                document.createElement(
                    "h3"
                );

            title.textContent =
                CATEGORY_LABELS[
                    category
                ] ?? category;

            section.appendChild(title);

            const list =
                document.createElement(
                    "div"
                );

            list.className =
                "inventory-list";

            for (const item of items) {
                const row =
                    document.createElement(
                        "div"
                    );

                row.className =
                    "inventory-item";

                const name =
                    document.createElement(
                        "strong"
                    );

                name.textContent =
                    item.name;

                const quantity =
                    document.createElement(
                        "span"
                    );

                quantity.textContent =
                    formatQuantity(
                        item.quantity,
                        item.unit
                    );

                row.append(
                    name,
                    quantity
                );

                list.appendChild(row);
            }

            section.appendChild(list);
            groupsContainer.appendChild(
                section
            );
        }

    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Impossible de charger l'inventaire.";

        errorElement.hidden = false;
    }
}


function optionList(
    values,
    selected,
    labels = {}
) {
    return values
        .map(value => `
            <option
                value="${value}"
                ${value === selected
                    ? "selected"
                    : ""}
            >
                ${escapeHtml(
                    labels[value] ?? value
                )}
            </option>
        `)
        .join("");
}


function renderWarnings(warnings) {
    warningsContainer.innerHTML = "";

    if (!warnings?.length) {
        return;
    }

    for (const warning of warnings) {
        const element =
            document.createElement("div");

        element.className =
            "alert warning";

        element.textContent =
            warning;

        warningsContainer.appendChild(
            element
        );
    }
}


function renderItems() {
    itemsContainer.innerHTML = "";

    document.getElementById(
        "review-count"
    ).textContent =
        `${detectedItems.length} produits`;

    detectedItems.forEach(
        (item, index) => {
            const row =
                document.createElement(
                    "div"
                );

            row.className =
                "food-item";

            const confidence =
                item.confidence === null ||
                item.confidence === undefined
                    ? "—"
                    : `${Math.round(
                        item.confidence * 100
                    )} %`;

            row.innerHTML = `
                <input
                    data-field="name"
                    data-index="${index}"
                    value="${escapeHtml(
                        item.name
                    )}"
                    placeholder="Produit"
                >

                <select
                    data-field="category"
                    data-index="${index}"
                >
                    ${optionList(
                        CATEGORIES,
                        item.category,
                        CATEGORY_LABELS
                    )}
                </select>

                <input
                    data-field="quantity"
                    data-index="${index}"
                    type="number"
                    min="0"
                    step="any"
                    value="${
                        item.quantity ?? ""
                    }"
                    placeholder="Quantité"
                >

                <select
                    data-field="unit"
                    data-index="${index}"
                >
                    ${optionList(
                        UNITS,
                        item.unit,
                        UNIT_LABELS
                    )}
                </select>

                <span class="confidence">
                    ${confidence}
                </span>

                <button
                    type="button"
                    class="icon-button danger"
                    data-delete="${index}"
                    title="Supprimer"
                >
                    ×
                </button>
            `;

            itemsContainer.appendChild(
                row
            );
        }
    );

    bindEditors();
}


function bindEditors() {
    document
        .querySelectorAll(
            "[data-field]"
        )
        .forEach(element => {
            element.addEventListener(
                "change",
                () => {
                    const index =
                        Number(
                            element.dataset
                                .index
                        );

                    const field =
                        element.dataset.field;

                    if (
                        field ===
                        "quantity"
                    ) {
                        detectedItems[
                            index
                        ][field] =
                            element.value === ""
                                ? null
                                : Number(
                                    element.value
                                );

                        return;
                    }

                    detectedItems[
                        index
                    ][field] =
                        element.value;
                }
            );
        });

    document
        .querySelectorAll(
            "[data-delete]"
        )
        .forEach(button => {
            button.addEventListener(
                "click",
                () => {
                    const index =
                        Number(
                            button.dataset
                                .delete
                        );

                    detectedItems.splice(
                        index,
                        1
                    );

                    renderItems();
                }
            );
        });
}


function renderPhotoPreview() {
    photoPreview.innerHTML = "";

    for (
        const file
        of imageInput.files
    ) {
        const item =
            document.createElement(
                "div"
            );

        item.className =
            "photo-preview-item";

        const image =
            document.createElement(
                "img"
            );

        const url =
            URL.createObjectURL(
                file
            );

        image.src = url;
        image.alt = file.name;

        image.addEventListener(
            "load",
            () => {
                URL.revokeObjectURL(
                    url
                );
            },
            {
                once: true
            }
        );

        item.appendChild(image);
        photoPreview.appendChild(
            item
        );
    }
}


imageInput.addEventListener(
    "change",
    renderPhotoPreview
);


form.addEventListener(
    "submit",
    async event => {
        event.preventDefault();

        if (
            imageInput.files.length ===
            0
        ) {
            setScanStatus(
                "Sélectionnez au moins une photo.",
                "error"
            );

            return;
        }

        const data =
            new FormData();

        for (
            const file
            of imageInput.files
        ) {
            data.append(
                "images",
                file
            );
        }

        analysisSection.hidden =
            true;

        detectedItems = [];
        currentScanId = null;

        scanButton.disabled = true;

        try {
            setScanStatus(
                "Envoi des photos…"
            );

            const upload =
                await fetchJson(
                    "/api/fridge/scans",
                    {
                        method: "POST",
                        body: data
                    }
                );

            currentScanId =
                upload.id;

            setScanStatus(
                "Analyse par l'IA en cours…"
            );

            const analyzed =
                await fetchJson(
                    `/api/fridge/scans/` +
                    `${currentScanId}/analyze`,
                    {
                        method: "POST"
                    }
                );

            detectedItems =
                analyzed.analysis.items;

            renderWarnings(
                analyzed.analysis.warnings
            );

            renderItems();

            analysisSection.hidden =
                false;

            setScanStatus(
                `${detectedItems.length} ` +
                `produits détectés. ` +
                `Vérifiez-les avant confirmation.`,
                "success"
            );

            analysisSection
                .scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

        } catch (error) {
            console.error(error);

            setScanStatus(
                `Échec du scan : ${error.message}`,
                "error"
            );

        } finally {
            scanButton.disabled =
                false;
        }
    }
);


document
    .getElementById("add-item")
    .addEventListener(
        "click",
        () => {
            detectedItems.push({
                name: "",
                category: "other",
                quantity: null,
                unit: "unknown",
                confidence: null,
                notes: null
            });

            renderItems();
        }
    );


confirmButton.addEventListener(
    "click",
    async () => {
        if (!currentScanId) {
            setScanStatus(
                "Aucun scan à confirmer.",
                "error"
            );

            return;
        }

        const invalid =
            detectedItems.some(
                item =>
                    !item.name ||
                    item.name.trim() === ""
            );

        if (invalid) {
            setScanStatus(
                "Tous les produits doivent avoir un nom.",
                "error"
            );

            return;
        }

        const items =
            detectedItems.map(
                item => ({
                    name:
                        item.name.trim(),
                    category:
                        item.category,
                    quantity:
                        item.quantity,
                    unit:
                        item.unit,
                    notes:
                        item.notes ?? null
                })
            );

        confirmButton.disabled =
            true;

        try {
            setScanStatus(
                "Enregistrement du nouvel inventaire…"
            );

            const response =
                await fetchJson(
                    `/api/fridge/scans/` +
                    `${currentScanId}/confirm`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body:
                            JSON.stringify({
                                items
                            })
                    }
                );

            setScanStatus(
                `Inventaire mis à jour : ` +
                `${response.inventory_count} produits.`,
                "success"
            );

            analysisSection.hidden =
                true;

            currentScanId = null;
            detectedItems = [];

            form.reset();
            photoPreview.innerHTML = "";

            await loadInventory();

        } catch (error) {
            console.error(error);

            setScanStatus(
                `Impossible de confirmer : ${error.message}`,
                "error"
            );

        } finally {
            confirmButton.disabled =
                false;
        }
    }
);


loadInventory();