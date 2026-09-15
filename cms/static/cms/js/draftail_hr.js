/*
 * « Ligne horizontale » (DIVIDER) et « Saut de page » (PAGE_BREAK) de l'éditeur riche du
 * blog (cms/wagtail_hooks.py) : deux entités personnalisées au rendu identique (<hr/>)
 * mais à l'effet différent — seule la seconde coupe l'article en pages
 * (BlogPostPage.get_context). Contrairement à « Galerie de photos »
 * (draftail_gallery.js), pas de fenêtre de choix ici : au clic sur le bouton, la source
 * insère directement le bloc et termine aussitôt (componentDidMount), sur le modèle de
 * la ligne horizontale intégrée de Draftail lui-même — que Wagtail n'expose que comme un
 * commutateur unique, d'où cette réimplémentation pour en avoir deux variantes.
 */
(function () {
  "use strict";

  function makeSource(entityType) {
    return class ImmediateInsertSource extends window.React.Component {
      componentDidMount() {
        const { editorState, onComplete } = this.props;
        const content = editorState.getCurrentContent();
        const contentWithEntity = content.createEntity(entityType, "IMMUTABLE", {});
        const entityKey = contentWithEntity.getLastCreatedEntityKey();
        const nextState = window.DraftJS.AtomicBlockUtils.insertAtomicBlock(editorState, entityKey, " ");
        onComplete(nextState);
      }

      render() {
        return null;
      }
    };
  }

  function makeDecorator(className) {
    return function HrDecorator() {
      return window.React.createElement("hr", { className: className });
    };
  }

  window.draftail.registerPlugin(
    { type: "DIVIDER", source: makeSource("DIVIDER"), decorator: makeDecorator("Draftail-hr") },
    "entityTypes",
  );

  window.draftail.registerPlugin(
    {
      type: "PAGE_BREAK",
      source: makeSource("PAGE_BREAK"),
      decorator: makeDecorator("Draftail-hr Draftail-hr--pagebreak"),
    },
    "entityTypes",
  );
})();
