// Number of extra artist roles
// This should be consistent with "extra" value provided on formset creation
let extraRows = 10;

function hideExtraArtistRoleForms(containerId) {
  let rolesContainer = document.getElementById(containerId);
  let artistRoleForms = rolesContainer.getElementsByClassName('artist-role-form');
  for (let i = 1; i <= extraRows; i++) {
    let artistRoleForm = artistRoleForms[artistRoleForms.length - i];
    artistRoleForm.style.display = "none";
  }
}

function showArtistRoleForm(containerId) {
  let rolesContainer = document.getElementById(containerId);
  let artistRoles = rolesContainer.getElementsByClassName('artist-role-form');
  for (let i = 0; i <= artistRoles.length; i++) {
    if (artistRoles[i].style.display === "none"){
      artistRoles[i].style.display = "flex";
      return;
    }
  }
}

