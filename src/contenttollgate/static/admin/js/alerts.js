(function($) {
 $(document).ready(function() {
   setTimeout(function() {
    $(".alert-success").fadeTo(500, 0).slideUp(500,
      function(){
        $(this).remove();
      });
    }, 2000);
 });
}(django.jQuery));
