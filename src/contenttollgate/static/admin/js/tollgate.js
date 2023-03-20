(function ($) {
  $(document).ready(function() {
    let metaLangSelector = ".field-meta_language > .related-widget-wrapper > select";

    function debounce(wait) {
      const STATUS_PENDING = 1;
      const STATUS_DONE = 2;

      return {
        status: STATUS_PENDING,
        timeout: null,
        isDone: function () {
          return this.state === STATUS_DONE;
        },
        reset: function () {
          this.status = STATUS_PENDING;
        },
        execute: function (target) {
          let args = this;
          let later = function () {
            args.timeout = null;
            args.status = STATUS_DONE;
            console.log(".......... form submitted");
            target.submit();
          };

          args.status = STATUS_PENDING;
          clearTimeout(this.timeout);
          args.timeout = setTimeout(later, wait);
        }
      }
    }

    let submit = debounce(250);

    $("form").submit(function (e) {
      // debounce multiple form submission
      if (submit.isDone() === false) {
        e.preventDefault();
        e.stopPropagation();
        submit.execute(e.target);
        return;
      }

      submit.reset();
    });

    // Sets all Songs meta_language value to that of the Release's meta_language
    $("#release").on('change', metaLangSelector, function () {
      let lang_id = $(this).val();
      let selects = $("#songs-group").find(metaLangSelector);
      selects.each(function (idx) {
        $(selects[idx]).val(lang_id);
      });
    });
  });
})(django.jQuery);
