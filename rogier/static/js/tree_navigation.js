/**
 * Rogier — Navigation dans l'arbre hiérarchique.
 *
 * Progressive enhancement : collapse/expand des noeuds conteneurs.
 * L'arbre fonctionne sans JS (tous les noeuds sont des liens).
 */
(function () {
    "use strict";

    // Clic sur les chevrons pour toggle un noeud
    document.querySelectorAll(".tree-chevron").forEach(function (chevron) {
        chevron.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var li = chevron.closest(".tree-item");
            var children = li.querySelector(".tree-children");
            if (!children) return;
            var isCollapsed = children.classList.contains("tree-children--collapsed");
            if (isCollapsed) {
                children.classList.remove("tree-children--collapsed");
                chevron.classList.add("tree-chevron--open");
            } else {
                children.classList.add("tree-children--collapsed");
                chevron.classList.remove("tree-chevron--open");
            }
        });
    });

    // Bouton "Tout developper"
    var expandBtn = document.getElementById("expand-all");
    if (expandBtn) {
        expandBtn.addEventListener("click", function () {
            document.querySelectorAll(".tree-children--collapsed").forEach(function (el) {
                el.classList.remove("tree-children--collapsed");
            });
            document.querySelectorAll(".tree-chevron").forEach(function (el) {
                el.classList.add("tree-chevron--open");
            });
        });
    }

    // Bouton "Tout replier"
    var collapseBtn = document.getElementById("collapse-all");
    if (collapseBtn) {
        collapseBtn.addEventListener("click", function () {
            document.querySelectorAll(".tree-children").forEach(function (el) {
                el.classList.add("tree-children--collapsed");
            });
            document.querySelectorAll(".tree-chevron").forEach(function (el) {
                el.classList.remove("tree-chevron--open");
            });
        });
    }

    // Scroll vers le noeud selectionne
    var selected = document.querySelector(".tree-item--selected");
    if (selected) {
        // S'assurer que les parents sont ouverts
        var parent = selected.parentElement;
        while (parent) {
            if (parent.classList && parent.classList.contains("tree-children--collapsed")) {
                parent.classList.remove("tree-children--collapsed");
                var parentLi = parent.closest(".tree-item");
                if (parentLi) {
                    var ch = parentLi.querySelector(":scope > .tree-chevron");
                    if (ch) ch.classList.add("tree-chevron--open");
                }
            }
            parent = parent.parentElement;
        }
        selected.scrollIntoView({ block: "center", behavior: "instant" });
    }
})();
