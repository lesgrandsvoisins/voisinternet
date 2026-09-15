/* Voisinternet — petits comportements ; le site fonctionne sans JavaScript. */
(function () {
  "use strict";

  function armToasts() {
    document.querySelectorAll(".toast").forEach(function (toast) {
      if (toast.dataset.armed) return;
      toast.dataset.armed = "1";
      var close = document.createElement("button");
      close.type = "button";
      close.className = "toast-close";
      close.setAttribute("aria-label", "Fermer le message");
      close.textContent = "×";
      close.addEventListener("click", function () { toast.remove(); });
      toast.appendChild(close);
      // Le numéro de compte reste affiché jusqu'à ce qu'on le ferme : il ne sera plus jamais montré.
      if (!toast.classList.contains("toast-number")) {
        setTimeout(function () { toast.remove(); }, 6000);
      }
    });
  }

  // Éditeur de description enrichi (fiches de l'annuaire) : surcouche visuelle d'un
  // <textarea> Markdown/HTML classique, qui reste la source de vérité soumise au serveur.
  // Sans JavaScript, le textarea et son aperçu Markdown restent affichés tels quels.
  var WYSIWYG_TAGS = ["p", "br", "hr", "strong", "em", "b", "i", "u", "s", "del",
    "a", "ul", "ol", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"];
  var WYSIWYG_ATTRS = { a: ["href", "title"] };

  var WYSIWYG_BLOCK_TAGS = ["p", "ul", "ol", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"];

  function sanitizeWysiwyg(root) {
    // Ne garde que les balises/attributs acceptés côté serveur (voir markdown_filters.py) :
    // ce que la personne voit dans l'éditeur doit correspondre à ce qui sera enregistré.
    root.querySelectorAll("*").forEach(function (el) {
      var tag = el.tagName.toLowerCase();
      if (WYSIWYG_TAGS.indexOf(tag) === -1) {
        while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
        el.remove();
        return;
      }
      var allowed = WYSIWYG_ATTRS[tag] || [];
      Array.from(el.attributes).forEach(function (attr) {
        if (allowed.indexOf(attr.name) === -1) el.removeAttribute(attr.name);
      });
    });
    // Chrome imbrique parfois une liste (ou un titre/une citation) dans le <p> en cours :
    // nesting invalide qu'un navigateur tolère en édition mais que le HTML n'autorise pas
    // (le serveur le corrigerait de son côté en laissant des <p></p> vides autour).
    root.querySelectorAll("p").forEach(function (p) {
      var hasBlockChild = Array.from(p.children).some(function (c) {
        return WYSIWYG_BLOCK_TAGS.indexOf(c.tagName.toLowerCase()) !== -1;
      });
      if (hasBlockChild) {
        while (p.firstChild) p.parentNode.insertBefore(p.firstChild, p);
        p.remove();
      }
    });
  }

  function armWysiwyg() {
    document.querySelectorAll("textarea[data-wysiwyg]").forEach(function (textarea) {
      if (textarea.dataset.wysiwygArmed) return;
      textarea.dataset.wysiwygArmed = "1";

      var wrap = textarea.closest(".wysiwyg");
      var toolbar = wrap.querySelector(".wysiwyg-toolbar");
      var editor = wrap.querySelector(".wysiwyg-editor");
      var fallback = wrap.parentElement.querySelector(".markdown-fallback");
      var preview = fallback ? fallback.querySelector(".markdown-preview") : null;

      document.execCommand("defaultParagraphSeparator", false, "p");
      editor.innerHTML = (preview && preview.innerHTML.trim()) ? preview.innerHTML : "<p><br></p>";
      sanitizeWysiwyg(editor);

      function sync() {
        sanitizeWysiwyg(editor);
        var text = editor.textContent.trim();
        textarea.value = text ? editor.innerHTML : "";
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
      }

      editor.addEventListener("input", sync);
      editor.addEventListener("blur", sync);
      editor.addEventListener("paste", function (e) {
        e.preventDefault();
        var text = (e.clipboardData || window.clipboardData).getData("text/plain");
        document.execCommand("insertText", false, text);
      });

      toolbar.querySelectorAll("button[data-cmd]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          editor.focus();
          var cmd = btn.dataset.cmd;
          if (cmd === "link") {
            var url = window.prompt("Adresse du lien (https://…) :", "https://");
            if (url) document.execCommand("createLink", false, url);
          } else {
            document.execCommand(cmd, false, btn.dataset.value || null);
          }
          sync();
        });
      });

      textarea.hidden = true;
      toolbar.hidden = false;
      editor.hidden = false;
      if (fallback) fallback.hidden = true;
    });
  }

  // Glisser-déposer sur les listes de raccourcis/groupes (core/partials/{shortcut,
  // membership}_list.html) : complète les boutons ↑/↓, qui restent la seule façon de
  // réordonner sans JavaScript.
  function armDragReorder() {
    document.querySelectorAll("[data-reorder]").forEach(function (list) {
      if (list.dataset.dragArmed) return;
      list.dataset.dragArmed = "1";

      var dragging = null;

      list.addEventListener("dragstart", function (e) {
        var li = e.target.closest("li[data-slug]");
        if (!li) return;
        dragging = li;
        li.classList.add("dragging");
      });

      list.addEventListener("dragend", function () {
        if (dragging) dragging.classList.remove("dragging");
        dragging = null;
      });

      list.addEventListener("dragover", function (e) {
        var li = e.target.closest("li[data-slug]");
        if (!dragging || !li || li === dragging) return;
        e.preventDefault();
        var rect = li.getBoundingClientRect();
        var before = (e.clientY - rect.top) < rect.height / 2;
        list.insertBefore(dragging, before ? li : li.nextSibling);
      });

      list.addEventListener("drop", function (e) {
        e.preventDefault();
        if (!dragging) return;

        var order = Array.from(list.querySelectorAll(":scope > li[data-slug]")).map(function (li) {
          return li.dataset.slug;
        });
        var csrfInput = list.querySelector("[name=csrfmiddlewaretoken]");
        if (!csrfInput) return;

        fetch(list.dataset.reorderUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrfInput.value,
          },
          body: "order=" + encodeURIComponent(order.join(",")),
        }).then(function (response) {
          return response.text();
        }).then(function (html) {
          var target = list.closest("[id]");
          if (target) target.innerHTML = html;
          armDragReorder();
        });
      });
    });
  }

  // Lightbox pour les photos d'un article de blog : sans JS, ce sont de simples images
  // dans le texte, cliquables uniquement vers elles-mêmes (aucune fonctionnalité perdue).
  var lightboxEl = null;
  var lightboxImages = [];
  var lightboxIndex = 0;

  function buildLightbox() {
    if (lightboxEl) return lightboxEl;
    var el = document.createElement("div");
    el.className = "lightbox";
    el.hidden = true;
    el.innerHTML =
      '<button type="button" class="lightbox-close" aria-label="Fermer">×</button>' +
      '<button type="button" class="lightbox-prev" aria-label="Image précédente">‹</button>' +
      '<img class="lightbox-img" alt="">' +
      '<button type="button" class="lightbox-next" aria-label="Image suivante">›</button>';
    document.body.appendChild(el);
    lightboxEl = el;
    return el;
  }

  function showLightboxImage() {
    var multiple = lightboxImages.length > 1;
    lightboxEl.querySelector(".lightbox-img").src = lightboxImages[lightboxIndex].src;
    lightboxEl.querySelector(".lightbox-prev").hidden = !multiple;
    lightboxEl.querySelector(".lightbox-next").hidden = !multiple;
  }

  function openLightbox(images, index) {
    var el = buildLightbox();
    lightboxImages = images;
    lightboxIndex = index;
    showLightboxImage();
    el.hidden = false;
    el.querySelector(".lightbox-close").focus();
  }

  function closeLightbox() {
    if (!lightboxEl) return;
    lightboxEl.hidden = true;
  }

  function stepLightbox(delta) {
    lightboxIndex = (lightboxIndex + delta + lightboxImages.length) % lightboxImages.length;
    showLightboxImage();
  }

  function armLightbox() {
    // La prévisualisation d'un article dans l'admin Wagtail affiche ce même template
    // dans une iframe : le lightbox n'y a rien à faire, il gênerait la modification de
    // l'image (clic qui ouvre le lightbox plutôt que la modifier).
    if (window.self !== window.top) return;
    document.querySelectorAll(".blog-post .markdown").forEach(function (container) {
      if (container.dataset.lightboxArmed) return;
      container.dataset.lightboxArmed = "1";
      var images = Array.from(container.querySelectorAll("img"));
      images.forEach(function (img, index) {
        img.classList.add("lightbox-trigger");
        img.addEventListener("click", function () { openLightbox(images, index); });
      });
    });
  }

  document.addEventListener("click", function (e) {
    if (!lightboxEl || lightboxEl.hidden) return;
    if (e.target.closest(".lightbox-close") || e.target === lightboxEl) closeLightbox();
    else if (e.target.closest(".lightbox-prev")) stepLightbox(-1);
    else if (e.target.closest(".lightbox-next")) stepLightbox(1);
  });

  document.addEventListener("keydown", function (e) {
    if (!lightboxEl || lightboxEl.hidden) return;
    if (e.key === "Escape") closeLightbox();
    else if (e.key === "ArrowLeft") stepLightbox(-1);
    else if (e.key === "ArrowRight") stepLightbox(1);
  });

  // Le menu principal et le widget du compte (en-tête) sont gérés par Alpine.js (voir base.html).
  document.addEventListener("DOMContentLoaded", armToasts);
  document.addEventListener("htmx:afterSettle", armToasts);
  document.addEventListener("DOMContentLoaded", armWysiwyg);
  document.addEventListener("htmx:afterSettle", armWysiwyg);
  document.addEventListener("DOMContentLoaded", armDragReorder);
  document.addEventListener("htmx:afterSettle", armDragReorder);
  document.addEventListener("DOMContentLoaded", armLightbox);
  document.addEventListener("htmx:afterSettle", armLightbox);
})();
