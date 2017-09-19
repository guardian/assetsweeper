from . import BaseProvider,LookupError


class Provider(BaseProvider):
    def lookup(self,filepath,filename,match_data):
        rtn = {}

        rtn['gnm_asset_category'] = "ITN Source"
        rtn['gnm_asset_restrictions_apply'] = "ITN source material. Check with Jacqui or Anna."
        rtn['gnm_asset_restrictions_notes'] = "REQUIRES REPORTING TO ITN"
        rtn['gnm_mm_provider'] = "ITN Source"
        rtn['gnm_mm_ref'] = match_data.group('itn_longid')
        rtn['CopyrightandLegalInformation'] = {
            'gnm_copyright_legal_copyright': 'ITN Source',
            'gnm_copyright_legal_provider_clip_id': match_data.group('itn_shortid'),
        }
        rtn['RightsProfileInformation'] = {
            'ContributorType': {
                'gnm_contributor_type_id': 48,
                'gnm_contributor_type_name': 'Footage Provider'
            },
            'Contributor': {
                'gnm_contributor_name': 'Independent Television News',
                'gnm_contributor_id': 'GNL037337'
            }
        }
        return rtn