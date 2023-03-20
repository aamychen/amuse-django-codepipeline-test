$(document).ready(function() {
  // Automatically update song genre when changes on release level
  let release_genre_id = "#id_release-genre"
  $(release_genre_id).on('change', function () {
    let song_genres = $('select[id^="id_song"][id$="genre"]');
    song_genres.each(function (idx) {
      let new_genre = $(release_genre_id).val();
      $(song_genres[idx]).val(new_genre).change();
    });
  });

  // Automatically update song meta-language when changes on release level
  let release_metalang_id = "#id_release-meta_language"
  $(release_metalang_id).on('change', function () {
    let song_genres = $('select[id^="id_song"][id$="meta_language"]');
    song_genres.each(function (idx) {
      let new_genre = $(release_metalang_id).val();
      $(song_genres[idx]).val(new_genre).change();
    });
  });

  // Show/hide large cover art on hover
  $('#cover-art').on({
    mouseenter: function() {
      $("#large-cover-art").show();
    },
    mouseleave: function() {
      $("#large-cover-art").hide();
    }
  });

  // Set text colour of release status dynamically
  function setReleaseStatusColour(value, object){
    let colour = 'white';
    switch (value) {
      case '3':   // Pending Approval
        colour = '#F5E96D'
        break;
      case '4':   // Approved
        colour = '#88CC88'
        break;
      case '6':   // Delivered
        colour = '#4CBB17'
        break;
      case '8': // Released
        colour = '#228B22'
        break;
      case '5':   // Not approved
      case '9':   // Rejected
        colour = '#FF9191'
        break;
    }
    object.css('background-color', colour);
  }

  let releaseStatusSelector = $('#id_release-status')
  setReleaseStatusColour(releaseStatusSelector.val(),releaseStatusSelector)
  releaseStatusSelector.on('change', function () {
    setReleaseStatusColour(releaseStatusSelector.val(), releaseStatusSelector)
  });

  let releaseStatusSidebar = $('#release-status-sidebar')
  setReleaseStatusColour(releaseStatusSelector.val(), releaseStatusSidebar)

  // Set border colour of song explicit value dynamically
  function setExplicitColour(value, object){
    let colour = '1px solid #ced4da';
    switch (value) {
      case '1':   // Explicit
        colour = '2px solid #F5E96D'
        break;
      case '2':   // Clean
        colour = '2px solid #FF9191'
        break;
    }
    object.style.border  = colour;
  }

  function updateExplicitColours(explicitSelector){
    explicitSelector.each(function( ) {
      setExplicitColour(this.value, this)
    })
  }

  let explicitSelector = $('select[id^="id_song-"][id$="-explicit"]');
  updateExplicitColours(explicitSelector);

  explicitSelector.on('change', function () {
    updateExplicitColours(explicitSelector);
  });

  // Set border colour of song origin value dynamically
  function setSongOriginColour(value, object){
    let colour = '1px solid #ced4da';
    switch (value) {
      case '2':   // Cover
        colour = '2px solid #F5E96D'
        break;
      case '3':   // Remix
        colour = '2px solid #FF9191'
        break;
    }
    object.style.border = colour;
  }

  function updateSongOriginColours(songOriginSelector){
    songOriginSelector.each(function( ) {
      setSongOriginColour(this.value, this)
    })
  }

  let songOriginSelector = $('select[id^="id_song-"][id$="-origin"]');
  updateSongOriginColours(songOriginSelector);

  songOriginSelector.on('change', function () {
    updateSongOriginColours(songOriginSelector);
  });


  // Set border colour of Youtube CID value dynamically
  function setYoutubeCIDColour(value, object){
    let colour = '1px solid #ced4da';
    switch (value) {
      case '0':   // None
        colour = '2px solid #C1FF9A'
        break;
      case '1':   // Block
        colour = '2px solid #F5E96D'
        break;
      case '2':   // Monetize
        colour = '2px solid #FF9191'
        break;
    }
    object.style.border = colour;
  }

  function updateYoutubeCIDColours(youtubeCIDSelector){
    youtubeCIDSelector.each(function( ) {
      setYoutubeCIDColour(this.value, this)
    })
  }

  let youtubeCIDSelector = $('select[id^="id_song-"][id$="-youtube_content_id"]');

  updateYoutubeCIDColours(youtubeCIDSelector);
  youtubeCIDSelector.on('change', function () {
    updateYoutubeCIDColours(youtubeCIDSelector);
  });


  function setSongArtistRolesHighlighting(value, object){
    let fontWeight = 'normal';
    switch (value) {
      case '1':   // Primary Artist
      case '2':   // Featuring Artist
      case '6':   // Remixer
        fontWeight = 'bold'
        break;
    }
    object.style.fontWeight = fontWeight;
  }

  function updateSongArtistRoleHighlighting(songArtistRoleSelector){
    songArtistRoleSelector.each(function( ) {
      setSongArtistRolesHighlighting(this.value, this)
    })
  }

  let songArtistRoleSelector = $('select[id^="id_song_artist_role"][id$="-role"]');

  updateSongArtistRoleHighlighting(songArtistRoleSelector);
  songArtistRoleSelector.on('change', function () {
    updateSongArtistRoleHighlighting(songArtistRoleSelector);
  });

  function setReleaseGenreHighlighting(value, object){
    let colour = '1px solid #ced4da';

    // Highlight: Soundtrack (22), Foreign Cinema (461), Musicals (462),
    // Original Score (463), TV Soundtrack (464), Alternative Rock (155), Metal (394),
    // Latino (436), Classical (5), Inspirational (13), Spoken Word (23)
    if ([22, 461, 462, 463, 464, 155, 394, 436, 5, 13, 23].includes(parseInt(value))){
        colour = '2px solid #FF9191';
    }
    object.style.border = colour;
  }

  let releaseGenreSelector = $('select[id="id_release-genre"]');
  console.log(releaseGenreSelector);

  function updateReleaseGenreHighlighting(releaseGenreSelector){
    releaseGenreSelector.each(function( ) {
      setReleaseGenreHighlighting(this.value, this)
    });
  }

  updateReleaseGenreHighlighting(releaseGenreSelector);
  releaseGenreSelector.on('change', function() {
    updateReleaseGenreHighlighting(releaseGenreSelector);
  });


  function setVersionHighlighting(value, object){
    let colour = '1px solid #ced4da';
    let flaggedVersions = ["Live", "Karaoke", "Remix", "Au Vivo", "En Vivo"]

    if (flaggedVersions.includes(value.trim())){
        colour = '2px solid #FF9191';
    }
    object.style.border = colour;
  }

  function updateVersionHighlighting(releaseVersionSelector){
    releaseVersionSelector.each(function( ) {
      setVersionHighlighting(this.value, this)
    });
  }

  let releaseVersionSelector = $('input[id="id_release-release_version"]');

  updateVersionHighlighting(releaseVersionSelector);
  releaseVersionSelector.on('change', function() {
    updateVersionHighlighting(releaseVersionSelector);
  });

  let songVersionSelector = $('input[id^="id_song-"][id$="-version"]');

  updateVersionHighlighting(songVersionSelector);
  songVersionSelector.on('change', function() {
    updateVersionHighlighting(songVersionSelector);
  });

})
