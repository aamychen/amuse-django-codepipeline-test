(function($) {
 $(document).ready(function() {
        const ROLE_PRIMARY_ARTIST = "1";
        const PREFIX = "id_releaseartistrole_set-";
        const ROLE_SUFFIX = "-role";
        const MAIN_PRIMARY_ARTIST_SUFFIX = "-main_primary_artist";


        $("#releaseartistrole_set-group").ready(function(e) {
          for (var i=0; ; i++) {
                const roleTagID = "#" + PREFIX + i + ROLE_SUFFIX;
                const mainPrimaryArtistTagID = roleTagID.replace(ROLE_SUFFIX, MAIN_PRIMARY_ARTIST_SUFFIX);

                const element = $(roleTagID);
                if (element.length == 0) {
                  break
                }

                $(mainPrimaryArtistTagID).prop('disabled', element.val() != ROLE_PRIMARY_ARTIST);
          }
        });


        $("#releaseartistrole_set-group").on( "change", function (e) {
          if (!e.target || !e.target.id) {
            return;
          }

          const id = e.target.id
          if (!id.startsWith(PREFIX)) {
            return;
          }

          if (!id.endsWith(ROLE_SUFFIX)) {
            return;
          }

          const mainPrimaryArtistTagID = "#" + id.replace(ROLE_SUFFIX, MAIN_PRIMARY_ARTIST_SUFFIX)
          $(mainPrimaryArtistTagID).prop('disabled', e.target.value != ROLE_PRIMARY_ARTIST);
        });


    });
}(django.jQuery));
