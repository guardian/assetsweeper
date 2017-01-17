from . import BaseProvider,LookupError


class Provider(BaseProvider):
    def lookup(self,filepath,filename,match_data):
        rtn = {}

        rtn['gnm_asset_category'] = "Reuters"
        rtn['gnm_asset_restrictions_apply'] = "true"
        rtn['gnm_asset_restrictions_notes'] = "Reuters news, covered by bulk deal. Contact Jacqui or Anna"
        rtn['gnm_mm_provider'] = "Reuters (via octopus tv)"
        rtn['CopyrightandLegalInformation'] = {
            'gnm_copyright_legal_copyright': 'Reuters',
        }
        rtn['RightsProfileInformation'] = {
            'ContributorType': {
                'gnm_contributor_type_id': 48,
                'gnm_contributor_type_name': 'Footage Provider'
            },
            'Contributor': {
                'gnm_contributor_name': 'Reuters Ltd',
                'gnm_contributor_id': 'GNL019992'
            }
        }
        return rtn