"""
Process the Android manifest file
"""

import xmltodict

def extract_activity_files(manifest_path):
    """Extract the files associated with activities (entry points to the application)
    Args:
        manifest_path: str - The path to the application manifest file
    Returns:
        [str] - The paths of the files associated with app activities
    """
    activity_files = []

    with open(manifest_path, "r") as manifest_file:
        manifest_data = manifest_file.read()
    
    manifest_dict = xmltodict.parse(manifest_data, force_list=('activity')) # force list on activity to handle single activity manifests

    application = manifest_dict['manifest']['application']
    activities = application['activity']
    
    for activity in activities:
        # format the path correctly
        try:
            path = "smali/" + activity['@android:name'].replace(".", "/") + ".smali"
            activity_files += [path]
        except Exception as e:
            print("####### Failed to extract activity path: \n{}\nManifest:\n{}".format(e, manifest_data))

    return activity_files


def extract_permissions(manifest_path):
    """Extract the permissions the app requests from the manifest file
    Args:
        manifest_path: str - The path to the application manifest file
    Returns:
        [str] - A list of requested permissions
    """
    permissions = []

    with open(manifest_path, "r") as manifest_file:
        manifest_data = manifest_file.read()

    manifest_dict = xmltodict.parse(manifest_data)
    
    try:
        permission_list = manifest_dict['manifest']['uses-permission']

        for permission in permission_list:
            permissions += [permission['@android:name'].split(".")[-1]] # just take the permission enum
    
    except Exception as e:
        pass
    
    finally:
        return permissions

