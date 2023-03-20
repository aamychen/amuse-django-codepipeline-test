from django.conf import settings
from googleplaces import GooglePlaces

google = GooglePlaces(settings.GOOGLE_SERVER_API_KEY)


def get_place_by_id(place_id):
    return google.get_place(place_id=place_id)


def get_country_by_place_id(place_id):
    place = get_place_by_id(place_id)
    if not place:
        return None
    place.get_details()
    for component in place.details.get('address_components'):
        if 'country' in component.get('types'):
            return component.get('short_name')
