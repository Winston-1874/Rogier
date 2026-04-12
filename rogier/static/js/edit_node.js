/**
 * Rogier — Édition inline des noeuds.
 *
 * Clic « Éditer » → textarea pré-remplie, boutons Enregistrer / Annuler.
 * Enregistrer → POST AJAX → bandeau vert 3s → rechargement page.
 *
 * TODO v0.2 : après édition, recharger uniquement le panneau droit
 * au lieu de location.reload(), pour préserver l'état dépliage de l'arbre.
 */
(function () {
    "use strict";

    var article = document.querySelector(".node-content");
    if (!article) return;

    var docHash = article.dataset.docHash;
    var nodePath = article.dataset.nodePath;
    var nodeKind = article.dataset.nodeKind;
    if (!nodePath) return; // racine : pas éditable

    var btnEdit = document.getElementById("btn-edit-node");
    if (!btnEdit) return;

    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

    btnEdit.addEventListener("click", function () {
        // Déterminer quel élément éditer
        var isArticle = (nodeKind === "ARTICLE");
        var editTarget;
        var originalText;

        if (isArticle) {
            editTarget = article.querySelector(".node-text");
            if (!editTarget) return;
            originalText = editTarget.textContent;
        } else {
            editTarget = article.querySelector(".node-title-text");
            if (!editTarget) {
                // Conteneur sans titre actuel : créer un placeholder
                var h2 = article.querySelector("h2");
                if (!h2) return;
                var span = document.createElement("span");
                span.className = "node-title-text";
                h2.appendChild(document.createTextNode(" — "));
                h2.appendChild(span);
                editTarget = span;
            }
            originalText = editTarget.textContent;
        }

        // Masquer le bouton Éditer
        btnEdit.style.display = "none";

        // Créer le formulaire d'édition
        var container = document.createElement("div");
        container.className = "edit-inline";

        var textarea = document.createElement("textarea");
        textarea.className = "edit-textarea";
        textarea.value = originalText;
        textarea.rows = isArticle ? 12 : 2;

        var actions = document.createElement("div");
        actions.className = "edit-actions";

        var btnSave = document.createElement("button");
        btnSave.type = "button";
        btnSave.className = "btn-small btn-save";
        btnSave.textContent = "Enregistrer";

        var btnCancel = document.createElement("button");
        btnCancel.type = "button";
        btnCancel.className = "btn-small";
        btnCancel.textContent = "Annuler";

        actions.appendChild(btnSave);
        actions.appendChild(btnCancel);
        container.appendChild(textarea);
        container.appendChild(actions);

        // Remplacer le contenu original
        editTarget.style.display = "none";
        editTarget.parentNode.insertBefore(container, editTarget.nextSibling);
        textarea.focus();

        // Annuler
        btnCancel.addEventListener("click", function () {
            container.remove();
            editTarget.style.display = "";
            btnEdit.style.display = "";
        });

        // Enregistrer
        btnSave.addEventListener("click", function () {
            btnSave.disabled = true;
            btnSave.textContent = "Enregistrement...";

            fetch("/document/" + docHash + "/node/edit", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify({
                    node_path: nodePath,
                    new_content: textarea.value
                })
            })
            .then(function (resp) {
                if (!resp.ok) {
                    return resp.json().then(function (data) {
                        throw new Error(data.detail || "Erreur serveur");
                    });
                }
                return resp.json();
            })
            .then(function (data) {
                // Bandeau de confirmation
                var banner = document.createElement("div");
                banner.className = "edit-success-banner";
                banner.textContent = "Version enregistree (" + data.version_id + ")";
                article.insertBefore(banner, article.firstChild);

                setTimeout(function () {
                    location.reload();
                }, 1500);
            })
            .catch(function (err) {
                var errBanner = document.createElement("div");
                errBanner.className = "edit-error-banner";
                errBanner.textContent = "Erreur : " + err.message;
                container.appendChild(errBanner);
                btnSave.disabled = false;
                btnSave.textContent = "Enregistrer";
            });
        });
    });
})();
