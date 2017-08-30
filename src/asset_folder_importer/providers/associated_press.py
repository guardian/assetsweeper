from . import BaseProvider,LookupError


class Provider(BaseProvider):
    def lookup(self,filepath,filename,match_data):
        return {
            'gnm_asset_category': 'Associated Press',
            'gnm_asset_restrictions_apply': "AP newswires content. For archive use contact info@aparchive.com",
            'gnm_mm_provider': 'Associated Press',
            'gnm_mm_ref': match_data.group('story_id'),
            'CopyrightandLegalInformation': {
                'gnm_copyright_legal_copyright': 'Associated Press',
                'gnm_copyright_legal_provider_clip_id': match_data.group('story_id'),
            },
            'RightsProfileInformation': {
                'ContributorType': {
                    'gnm_contributor_type_id': 48,
                    'gnm_contributor_type_name': 'Footage Provider'
                },
                'Contributor': {
                    'gnm_contributor_name': 'The Associated Press Ltd',
                    'gnm_contributor_id': 'GNL000761'
                }
            }
        }