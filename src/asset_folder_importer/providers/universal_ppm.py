from . import BaseProvider,LookupError


class Provider(BaseProvider):
    def lookup(self,filepath,filename,match_data):
        rtn = {}

        rtn['gnm_asset_category'] = "Universal Publishing Production Music"
        rtn['gnm_asset_restrictions_apply'] = "Universal Music, covered by bulk deal. Contact Jacqui or Anna"
        rtn['gnm_asset_restrictions_notes'] = "REQUIRES REPORTING TO UNIVERSAL"
        rtn['gnm_mm_provider'] = "Universal Publishing Production Music"
        rtn['gnm_mm_ref'] = match_data.group(0) #entire matched string
        rtn['CopyrightandLegalInformation'] = {
            'gnm_copyright_legal_copyright': 'Universal Publishing Production Music',
            'gnm_copyright_legal_provider_clip_id': match_data.group(0) #entire matched string,
        }
        rtn['RightsProfileInformation'] = {
            'ContributorType': {
                'gnm_contributor_type_id': 48,
                'gnm_contributor_type_name': 'Footage Provider'
            },
            'Contributor': {
                'gnm_contributor_name': 'Universal Music Publishing Ltd',
                'gnm_contributor_id': 'GNL509836'
            }
        }
        return rtn