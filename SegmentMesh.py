# Segments geometry into separate grid tiles
# Designed to be used with OSM building data

import bpy
from mathutils import Vector

#object_name = "Buildings"
#object_name = "Roads"
object_name = bpy.context.active_object.name
startX = -625.0
startY = -500.0
sizeX = 250.0
sizeY = 250.0
tileX = 5
tileY = 4

# Get the mesh object by its name
mesh_object = bpy.data.objects[object_name]
#mesh_object = bpy.context.active_object
mesh = mesh_object.data

print("Source 0: " + mesh_object.name)
print("Active 0: " + bpy.context.view_layer.objects.active.name)

min_x = 0.0
min_y = 0.0

for x in range(tileX):
    min_x = startX + (x * sizeX)
    max_x = min_x + sizeX
    for y in range(tileY):
        min_y = startY + (y * sizeY)
        max_y = min_y + sizeY
        
        print("")
        
        print("Min: " + str(min_x) + " x " + str(min_y))
        print("Max: " + str(max_x) + " x " + str(max_y))
        
        print("Source 1: " + mesh_object.name)
        print("Active 1: " + bpy.context.view_layer.objects.active.name)
        
        # Create tile name
        tile_name = mesh_object.name + "-Tile-" + str(x) + "-" + str(y)
        print(tile_name)
        
        # Count how many polygons have been selected
        count = 0
        
        # Select polygons within the specified XYZ area
        for polygon in mesh.polygons:
            # Find average vertex location (not bounding box or area, just super basic)
            centroid = Vector((0, 0, 0))
            for vertice_index in polygon.vertices:
                centroid += mesh.vertices[vertice_index].co
            centroid /= len(polygon.vertices)
            
            # Check polygon centre against min/max
            if min_x <= centroid.x <= max_x and min_y <= centroid.y <= max_y:
                polygon.select = True
                count += 1
            else:
                polygon.select = False
        
        print("Selected: " + str(count))
        
        # Only create a new segment if there are 1 or more polygons selected
        if count > 0:
            
            print("Active 2: " + mesh_object.name)
            print("Active 2: " + bpy.context.view_layer.objects.active.name)
            
            # Separate selected polygons into a new object
            bpy.context.view_layer.objects.active = mesh_object
            print("Active 3: " + mesh_object.name)
            print("Active 3: " + bpy.context.view_layer.objects.active.name)
            mesh_object.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')
            print("Active 4: " + mesh_object.name)
            print("Active 4: " + bpy.context.view_layer.objects.active.name)
            
            # Rename the separated object and mesh
            separated_object = bpy.context.selected_objects[1]
            separated_object.name = tile_name
            separated_mesh = separated_object.data
            separated_mesh.name = tile_name
            separated_object.select_set(False)
            
            print("Active 5: " + mesh_object.name)
            print("Active 5: " + bpy.context.view_layer.objects.active.name)
            
            print("")