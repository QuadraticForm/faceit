from .faceit_data import FACE_REGIONS_BASE


def get_index_from_path(shape_item_path):
    ''' Returns the index from path (integer in []) '''
    found_index = shape_item_path[shape_item_path.find('[') + 1:shape_item_path.find(']')]
    if found_index:
        found_index = int(found_index)
        return found_index
    else:
        return -1


def get_index_of_parent_collection_item(item):
    ''' Returns the index of the parent item of @item '''
    parent_path = item.path_from_id().split('.')[-2]
    return get_index_from_path(parent_path)


def get_index_of_collection_item(item):
    ''' Returns the index of the @item in the corresponding collection. '''
    path = item.path_from_id().split('.')[-1]
    return get_index_from_path(path)


def get_all_set_target_shapes(retarget_list, region=None):
    ''' Return a list of all target shapes registered to all arkit source shapes.
    @retarget_list: the collection property (either scene or fbx)
     '''
    all_target_shapes = []
    for item in retarget_list:
        if region:
            if item.region.lower() != region:
                continue
        target_shapes = item.target_shapes
        for target_item in target_shapes:
            all_target_shapes.append(target_item.name)
    return all_target_shapes


def is_target_shape_double(shape_name, retarget_list):
    ''' Check if the target shape with @shape_name has been registered to any Arkit shape'''
    all_target_shapes = get_all_set_target_shapes(retarget_list)
    return shape_name in all_target_shapes


def eval_target_shapes(retarget_list):
    '''Return True if any target shapes are populated for the specified list.'''
    target_shapes_initiated = False
    if retarget_list:
        target_shapes_initiated = any([(len(item.target_shapes) > 0) for item in retarget_list])
    return target_shapes_initiated


def get_target_shapes_dict(retarget_list, force_empty_strings=False):
    '''Returns a dict of arkit shape name and target shape based on retarget_list collectionprop'''

    target_shapes_dict = {}

    if retarget_list:

        for item in retarget_list:

            arkit_shape = item.name
            target_shapes = item.target_shapes
            target_shapes_list = [t.name for t in target_shapes]

            if target_shapes_list:
                target_shapes_dict[arkit_shape] = target_shapes_list
            else:
                if force_empty_strings:
                    target_shapes_dict[arkit_shape] = ['', ]
                # elif

    return target_shapes_dict


def set_base_regions_from_dict(retarget_list):
    # Get shape region
    for region, shapes in FACE_REGIONS_BASE.items():
        for shape_name in shapes:
            item = retarget_list.get(shape_name)
            if item:
                item.region = region
            # else:
            #     item.region = 'Other'


def get_all_set_target_shapes_regions(retarget_list):
    ''' Return a dict of all target shapes and the respective regions.
    @retarget_list: the collection property
     '''
    shape_region_dict = {
        'eyes': [],
        'brows': [],
        'cheeks': [],
        'nose': [],
        'mouth': [],
        'tongue': [],
        'other': [],
    }
    for item in retarget_list:
        target_shapes = item.target_shapes
        if not target_shapes:
            continue
        region = item.region.lower()
        for target_item in target_shapes:
            try:
                shape_region_dict[region].append(target_item.name)
            except KeyError:
                shape_region_dict[region] = [target_item.name, ]

            # if not shape_region_dict[region]:
    return shape_region_dict
