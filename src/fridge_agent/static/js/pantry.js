const PANTRY_UNITS = [
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


const PANTRY_UNIT_LABELS = {
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


let pantryItems = [];
let pantryDirty = false;


const itemsContainer =
    document.getElementById("pantry-items");

const countElement =
    document.getElementById("pantry-count");

const summaryElement =
    document.getElementById("pantry-summary");

const emptyElement =
    document.getElementById("pantry-empty");

const errorElement =
    document.getElementById("pantry-error");

const successElement =
    document.getElementById("pantry-success");

const dirtyElement =
    document.getElementById("pantry-dirty");

const saveButton =
    document.getElementById("save-pantry");


function escapeHtml(value) {
    const div =
        document.createElement("div");

    div.textContent = value ?? "";

    return div.innerHTML;
}


async function fetchJson(
    url,
    options = {}
) {
    const response = await fetch(
        url,
        options
    );

    if (!response.ok) {
        const message =
            await response.text();

        throw new Error(
            message ||
            `HTTP ${response.status}`
        );
    }

    return response.json();
}


function hideMessages() {
    errorElement.hidden = true;
    successElement.hidden = true;
}


function setDirty(value) {
    pantryDirty = value;
    dirtyElement.hidden = !value;
}


function unitOptions(selected) {
    return PANTRY_UNITS
        .map(unit => `
            <option
                value="${unit}"
                ${unit === selected
                    ? "selected"
                    : ""}
            >
                ${PANTRY_UNIT_LABELS[unit]}
            </option>
        `)
        .join("");
}


function renderPantry() {
    itemsContainer.innerHTML = "";

    countElement.textContent =
        pantryItems.length;

    summaryElement.textContent =
        `${pantryItems.length} produits suivis`;

    emptyElement.hidden =
        pantryItems.length !== 0;

    pantryItems.forEach(
        (item, index) => {
            const row =
                document.createElement(
                    "div"
                );

            row.className =
                "pantry-item";

            row.innerHTML = `
                <input
                    type="text"
                    value="${escapeHtml(
                        item.name
                    )}"
                    data-index="${index}"
                    data-field="name"
                    placeholder="Produit"
                >

                <input
                    type="number"
                    min="0"
                    step="any"
                    value="${
                        item.quantity ?? ""
                    }"
                    data-index="${index}"
                    data-field="quantity"
                    placeholder="Quantité"
                >

                <select
                    data-index="${index}"
                    data-field="unit"
                >
                    ${unitOptions(
                        item.unit
                    )}
                </select>

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

    bindPantryEditors();
}


function bindPantryEditors() {
    document
        .querySelectorAll(
            "#pantry-items [data-field]"
        )
        .forEach(element => {
            element.addEventListener(
                "input",
                () => {
                    const index =
                        Number(
                            element.dataset.index
                        );

                    const field =
                        element.dataset.field;

                    if (
                        field === "quantity"
                    ) {
                        pantryItems[
                            index
                        ].quantity =
                            element.value === ""
                                ? null
                                : Number(
                                    element.value
                                );

                        if (
                            element.value === ""
                        ) {
                            pantryItems[
                                index
                            ].unit =
                                "unknown";

                            renderPantry();
                        }

                    } else {
                        pantryItems[
                            index
                        ][field] =
                            element.value;
                    }

                    setDirty(true);
                    hideMessages();
                }
            );
        });

    document
        .querySelectorAll(
            "#pantry-items [data-delete]"
        )
        .forEach(button => {
            button.addEventListener(
                "click",
                () => {
                    const index =
                        Number(
                            button.dataset.delete
                        );

                    pantryItems.splice(
                        index,
                        1
                    );

                    setDirty(true);
                    hideMessages();
                    renderPantry();
                }
            );
        });
}


async function loadPantry() {
    hideMessages();

    try {
        const response =
            await fetchJson(
                "/api/pantry"
            );

        pantryItems =
            response.items.map(
                item => ({
                    name: item.name,
                    quantity:
                        item.quantity,
                    unit: item.unit
                })
            );

        renderPantry();

        setDirty(false);

    } catch (error) {
        console.error(error);

        errorElement.textContent =
            "Impossible de charger les placards.";

        errorElement.hidden = false;
    }
}


document
    .getElementById(
        "add-pantry-item"
    )
    .addEventListener(
        "click",
        () => {
            pantryItems.push({
                name: "",
                quantity: null,
                unit: "unknown"
            });

            setDirty(true);
            hideMessages();
            renderPantry();

            const inputs =
                itemsContainer
                    .querySelectorAll(
                        'input[data-field="name"]'
                    );

            inputs[
                inputs.length - 1
            ]?.focus();
        }
    );


saveButton.addEventListener(
    "click",
    async () => {
        hideMessages();

        const cleanedItems =
            pantryItems
                .map(item => ({
                    name:
                        item.name.trim(),
                    quantity:
                        item.quantity,
                    unit:
                        item.unit
                }))
                .filter(
                    item =>
                        item.name !== ""
                );

        if (
            cleanedItems.length !==
            pantryItems.length
        ) {
            errorElement.textContent =
                "Tous les produits doivent avoir un nom.";

            errorElement.hidden =
                false;

            return;
        }

        for (
            const item
            of cleanedItems
        ) {
            if (
                item.quantity === null
            ) {
                item.unit =
                    "unknown";
            }
        }

        saveButton.disabled =
            true;

        try {
            const response =
                await fetchJson(
                    "/api/pantry",
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body:
                            JSON.stringify({
                                items:
                                    cleanedItems
                            })
                    }
                );

            successElement.textContent =
                `Placards enregistrés : ` +
                `${response.count} produits.`;

            successElement.hidden =
                false;

            pantryItems =
                cleanedItems;

            setDirty(false);
            renderPantry();

        } catch (error) {
            console.error(error);

            errorElement.textContent =
                `Impossible d'enregistrer : ` +
                `${error.message}`;

            errorElement.hidden =
                false;

        } finally {
            saveButton.disabled =
                false;
        }
    }
);


window.addEventListener(
    "beforeunload",
    event => {
        if (!pantryDirty) {
            return;
        }

        event.preventDefault();
        event.returnValue = "";
    }
);


loadPantry();