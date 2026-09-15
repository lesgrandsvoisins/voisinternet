/*
 * Bouton « Galerie de photos » de l'éditeur riche (cms/wagtail_hooks.py). Comme les
 * autres « source » Draftail (voir la documentation Wagtail sur l'extension de
 * Draftail), ce n'est pas un vrai composant React visible : il ne fait que déclencher
 * une action au montage et n'affiche jamais rien lui-même.
 *
 * Différence avec le bouton « Image » natif : au lieu de refermer la fenêtre du
 * sélecteur après le premier choix, on la rouvre immédiatement pour la photo
 * suivante, jusqu'à ce que la personne la ferme elle-même. Chaque photo devient une
 * entité IMAGE tout à fait normale (mêmes règles de sauvegarde que le bouton natif) :
 * c'est le CSS (site.css) qui détecte plusieurs images consécutives et les met en grille.
 *
 * window.draftail.ImageModalWorkflowSource est une vraie classe ES6 (pas une fonction) :
 * il faut donc `class ... extends ...`, pas un bricolage de prototype à la main.
 */
(function () {
  "use strict";

  var ImageModalWorkflowSource = window.draftail.ImageModalWorkflowSource;

  class GalleryImageSource extends ImageModalWorkflowSource {
    constructor(props) {
      super(props);
      this.accumulatedState = props.editorState;
    }

    // Reprend content.createEntity() + AtomicBlockUtils.insertAtomicBlock() de
    // ModalWorkflowSource.onChosen(), mais à partir de l'état accumulé (pas seulement
    // this.props.editorState, qui ne change pas tant qu'on n'appelle pas onComplete) et
    // sans jamais appeler onComplete ni fermer définitivement — juste rouvrir le choix suivant.
    onChosen(data) {
      const entityData = this.filterEntityData(data);
      const content = this.accumulatedState.getCurrentContent();
      const selection = this.accumulatedState.getSelection();
      const contentWithEntity = content.createEntity("IMAGE", "IMMUTABLE", entityData);
      const entityKey = contentWithEntity.getLastCreatedEntityKey();
      const stateWithSelection = window.DraftJS.EditorState.forceSelection(this.accumulatedState, selection);
      this.accumulatedState = window.DraftJS.AtomicBlockUtils.insertAtomicBlock(stateWithSelection, entityKey, " ");

      if (this.workflow) this.workflow.close();
      this.openNextChooser();
    }

    openNextChooser() {
      const config = this.getChooserConfig();
      this.workflow = window.ModalWorkflow({
        url: config.url,
        urlParams: config.urlParams,
        onload: config.onload,
        responses: config.responses,
        onError: () => {
          // eslint-disable-next-line no-alert
          window.alert("Erreur serveur");
          this.finish();
        },
      });
    }

    // Fermeture de la fenêtre sans choisir de photo (croix, touche Échap…) : on arrête
    // là, en gardant toutes les photos déjà ajoutées dans cette session.
    onClose(e) {
      if (e && e.preventDefault) e.preventDefault();
      this.finish();
    }

    finish() {
      this.props.onComplete(this.accumulatedState);
    }
  }

  // Jamais réellement affiché : aucun bloc IMAGE_GALLERY n'est créé (onChosen ci-dessus
  // crée des entités IMAGE), seul le bouton de la barre d'outils utilise ce type. Requis
  // par Draftail pour valider l'enregistrement du type d'entité.
  function GalleryDecorator(props) {
    return props.children;
  }

  window.draftail.registerPlugin(
    {
      type: "IMAGE_GALLERY",
      source: GalleryImageSource,
      decorator: GalleryDecorator,
    },
    "entityTypes",
  );
})();
