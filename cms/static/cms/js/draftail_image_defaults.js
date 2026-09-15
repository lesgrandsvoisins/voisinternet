/*
 * Quand on insère une image dans un champ de texte enrichi (bouton natif « Image » ou
 * notre « Galerie de photos », draftail_gallery.js), aucun format n'est présélectionné :
 * Wagtail ne fixe volontairement pas d'`initial` sur ce champ (wagtail/images/forms.py,
 * ImageInsertionForm). Ici on présélectionne « Pleine largeur » par défaut — sauf quand
 * un format est déjà coché (on modifie une image déjà insérée : son format d'origine est
 * alors passé en paramètre et coché normalement par Wagtail, on n'y touche pas).
 *
 * Point d'accroche : ImageModalWorkflowSource.getChooserConfig() (Draftail, intégré à
 * Wagtail) passe toujours `onload: window.IMAGE_CHOOSER_MODAL_ONLOAD_HANDLERS` — le même
 * gestionnaire global, que ce soit le bouton natif ou une source qui en hérite comme la
 * nôtre — d'où l'idée d'étendre ce point plutôt que de dupliquer la logique par bouton.
 */
(function () {
  "use strict";

  function preselectFullWidth(modal) {
    var container = modal && modal.body && modal.body[0] ? modal.body[0] : document;
    var radios = container.querySelectorAll('input[name="image-chooser-insertion-format"]');
    for (var i = 0; i < radios.length; i++) {
      if (radios[i].checked) return;
    }
    for (var j = 0; j < radios.length; j++) {
      if (radios[j].value === "fullwidth") {
        radios[j].checked = true;
        return;
      }
    }
  }

  function patch() {
    var handlers = window.IMAGE_CHOOSER_MODAL_ONLOAD_HANDLERS;
    if (!handlers || handlers.__lgvFullwidthDefault) return false;

    var original = handlers.select_format;
    handlers.select_format = function (modal, jsonData) {
      if (original) original.call(this, modal, jsonData);
      preselectFullWidth(modal);
    };
    handlers.__lgvFullwidthDefault = true;
    return true;
  }

  if (!patch()) {
    document.addEventListener("DOMContentLoaded", patch);
  }
})();
