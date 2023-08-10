# https://www.ifacialmocap.com/for-developer/

def decode_ifacial_mocap(data, shape_reference):
    return convert_ifacial_mocap_to_face_cap_format(data.decode('utf-8'), shape_reference)


def convert_ifacial_mocap_to_face_cap_format(data, shape_reference):
    data = data.split('|')
    animation_data = []
    raw_shape_data = data[:52]
    for i, shape in enumerate(raw_shape_data):
        _shape_name, value = shape.split('-')
        i = shape_reference.index(_shape_name)
        value = float(value) / 100
        animation_data.append(('/W', (i, value)))
    head_data = data[53].split('#')[1].split(',')
    head_rotation = head_data[:3]
    animation_data.append(('/HR', [float(i) for i in head_rotation]))
    head_translation = head_data[3:]
    animation_data.append(('/HT', [float(i) for i in head_translation]))
    eye_left_data = data[54].split('#')[1].split(',')
    animation_data.append(('/ERL', [float(i) for i in eye_left_data]))
    eye_right_data = data[55].split('#')[1].split(',')
    animation_data.append(('/ERR', [float(i) for i in eye_right_data]))
    return animation_data