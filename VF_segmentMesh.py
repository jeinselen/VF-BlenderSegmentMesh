bl_info = {
	"name": "VF Segment Mesh",
	"author": "John Einselen - Vectorform LLC",
	"version": (0, 4, 0),
	"blender": (3, 6, 0),
	"location": "Scene > VF Tools > Segment Mesh",
	"description": "Divide meshes into grid based segments",
	"warning": "inexperienced developer, use at your own risk",
	"doc_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh",
	"tracker_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh/issues",
	"category": "3D View"}

import bpy
from mathutils import Vector
#import mathutils
import bmesh
#from bpy.app.handlers import persistent

###########################################################################
# Main class

class VF_SegmentMesh(bpy.types.Operator):
	bl_idname = "object.vf_segment_mesh"
	bl_label = "Segment Mesh"
	bl_description = "Divide large meshes into grid-based components for more efficient rendering in realtime game engines"
#	bl_options = {'REGISTER', 'UNDO'}
	
	def find_connected_elements(mesh, start_element_index, visited, min_x, min_y, max_x, max_y):
		stack = [start_element_index]
		connected_elements = set()
		
		while stack:
			element_index = stack.pop()
			if element_index not in visited:
				visited.add(element_index)
				connected_elements.add(element_index)
				for neighbor in mesh.polygons[element_index].vertices:
					for adjacent_element in mesh.vertices[neighbor].link_faces:
						if adjacent_element.index not in visited and min_x <= adjacent_element.center.x <= max_x and min_y <= adjacent_element.center.y <= max_y:
							stack.append(adjacent_element.index)
							
		return connected_elements
	
	def execute(self, context):
		# Set up local variables
		sizeX = bpy.context.scene.vf_segment_mesh_settings.tile_size[0]
		sizeY = bpy.context.scene.vf_segment_mesh_settings.tile_size[1]
		countX = bpy.context.scene.vf_segment_mesh_settings.tile_count[0]
		countY = bpy.context.scene.vf_segment_mesh_settings.tile_count[1]
		startX = sizeX * float(countX) * -0.5
		startY = sizeY * float(countY) * -0.5
		group = True if bpy.context.scene.vf_segment_mesh_settings.tile_segment == "GROUP" else False
		bounds = bpy.context.scene.vf_segment_mesh_settings.tile_bounds
		
		# Get active object by name (so the source object doesn't change during processing)
		# This is very silly, I just can't remember how to create a reference to the active object without it changing when the active object changes
		object_name = str(bpy.context.active_object.name)
		mesh_object = bpy.data.objects[object_name]
		mesh = mesh_object.data
		
		# Calculate island positions if we're not in per-polygon mode
		if group:
			# Convert the mesh to a BMesh for easier manipulation
			bm = bmesh.new()
			bm.from_mesh(mesh)
			
			# Create a custom vector polygon attribute to store the bounding box centers
			attr = bm.faces.layers.vec.new("BoundingBoxCenter")
			
			# Iterate through polygons to find mesh islands
			for face in bm.faces:
				# Check if the BoundingBoxCenter attribute exists on the current polygon
				if attr in face:
					# If the attribute exists, skip to the next polygon
					continue
				
				# Select the current face
				face.select_set(True)
				
				# Expand the selection to linked polygons
				bpy.ops.mesh.select_linked(delimit=set())
				
				# Get the selected polygons
				selected_polygons = [poly for poly in bm.faces if poly.select]
				
				# Calculate selected mesh island position, either average vertex or bounding box
				if True:
					# Calculate average vertex center
					vertices = [v.co for poly in selected_polygons for v in poly.verts]
					bounding_box_center = sum(vertices, mathutils.Vector()) / len(vertices)
				else:
					# Calculate bounding box minimmum and maximum extents
					min_coords = mathutils.Vector((float('inf'), float('inf'), float('inf')))
					max_coords = mathutils.Vector((-float('inf'), -float('inf'), -float('inf')))
					for poly in selected_polygons:
						for vert in poly.verts:
							min_coords.x = min(min_coords.x, vert.co.x)
							min_coords.y = min(min_coords.y, vert.co.y)
							min_coords.z = min(min_coords.z, vert.co.z)
							max_coords.x = max(max_coords.x, vert.co.x)
							max_coords.y = max(max_coords.y, vert.co.y)
							max_coords.z = max(max_coords.z, vert.co.z)
					# Calculate bounding box center
					bounding_box_center = (min_coords + max_coords) / 2
				
				# Mark the selected polygons as processed by storing the mesh island center point
				for poly in bm.faces:
					if poly.select:
						poly[attr] = bounding_box_center
						
			# Clean up the mesh by removing the BoundingBoxCenter attribute
			# I think ChatGPT lied about this!
			bm.faces.layers.remove(attr)
			
			# Update the mesh with the changes from the BMesh
			bm.to_mesh(mesh)
			bm.free()
		
		# Loop through each grid space
		for x in range(countX):
			# Define min/max for X
			min_x = startX + (x * sizeX)
			max_x = min_x + sizeX
			if bounds:
				if y == 0:
					min_x = float('-inf')
				elif y == countY-1:
					max_x = float('inf')
			
			for y in range(countY):
				# Define min/max for Y
				min_y = startY + (y * sizeY)
				max_y = min_y + sizeY
				if bounds:
					if y == 0:
						min_y = float('-inf')
					elif y == countY-1:
						max_y = float('inf')
				
				# Create tile name
				tile_name = mesh_object.name + "-Tile-" + str(x) + "-" + str(y)
				
				# Count how many polygons have been selected
				count = 0
				
				# Create selection
				if group:
					# Find connected elements within the specified XYZ area
					visited_elements = set()
					for element_index in range(len(mesh.polygons)):
						if element_index not in visited_elements:
							# Find connected elements and test if group
							connected_elements = find_connected_elements(mesh, element_index, visited_elements, min_x, min_y, max_x, max_y)
							center_of_mass = sum(mesh.polygons[index].center for index in connected_elements) / len(connected_elements)
							
							if min_x <= center_of_mass.x <= max_x and min_y <= center_of_mass.y <= max_y:
								# Separate connected elements into a new object
								bpy.ops.object.mode_set(mode='EDIT')
								bpy.ops.mesh.select_all(action='DESELECT')
								for index in connected_elements:
									mesh.polygons[index].select = True
								bpy.ops.mesh.separate(type='SELECTED')
								bpy.ops.object.mode_set(mode='OBJECT')
								
								# Get the separated object and rename it
								separated_object = bpy.context.view_layer.objects.active
								separated_object.name = separated_object_name
								
								# Rename the separated mesh
								separated_mesh = separated_object.data
								separated_mesh.name = separated_mesh_name
								
								# Deselect the separated object
								separated_object.select_set(False)
				else:
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
						
				# Only create a new segment if there are 1 or more polygons selected
				if count > 0:
					# Separate selected polygons into a new object
					bpy.context.view_layer.objects.active = mesh_object
					mesh_object.select_set(True)
					bpy.ops.object.mode_set(mode='EDIT')
					bpy.ops.mesh.separate(type='SELECTED')
					bpy.ops.object.mode_set(mode='OBJECT')
					
					# Rename the separated object and mesh
					separated_object = bpy.context.selected_objects[1]
					separated_object.name = tile_name
					separated_mesh = separated_object.data
					separated_mesh.name = tile_name
					separated_object.select_set(False)
		
		# Done
		return {'FINISHED'}

def VF_SegmentMeshPreview(self, context):
	# Remove existing mesh data block (and associated object) if it exists
	if mesh_name in bpy.data.meshes:
		mesh = bpy.data.meshes[mesh_name]
		bpy.data.meshes.remove(mesh)
		bpy.data.meshes.remove(bpy.data.meshes[mesh_name])
	
	# Stop now if the preview mesh is disabled
	if bpy.context.scene.vf_segment_mesh_settings.show_preview:
		# Done
		return {'FINISHED'}
	
	# Set up local variables
	sizeX = bpy.context.scene.vf_segment_mesh_settings.tile_size[0]
	sizeY = bpy.context.scene.vf_segment_mesh_settings.tile_size[1]
	countX = bpy.context.scene.vf_segment_mesh_settings.tile_count[0]
	countY = bpy.context.scene.vf_segment_mesh_settings.tile_count[1]
	mesh_name = "vf_segment_mesh_preview_temp"
	
	# Save the current object selection
	active_object_name = str(bpy.context.active_object.name)
	selected_objects = [obj for obj in bpy.context.selected_objects]
	
	# Create primitive grid
	bpy.ops.mesh.primitive_grid_add(
		x_subdivisions=countX,
		y_subdivisions=countY,
		size=1,
		enter_editmode=False,
		align='WORLD',
		location=(0.0, 0.0, 0.0),
		rotation=(0.0, 0.0, 0.0),
		scale=(sizeX * countX, sizeY * countY, 1.0))
	
	# Set scale
	bpy.context.active_object.scale = (sizeX * countX, sizeY * countY, 1.0)
	bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
	
	# Rename object and mesh data block
	bpy.context.active_object.name = mesh_name
	bpy.context.active_object.data.name = mesh_name
	
	# Reset selection
	bpy.context.active_object.select_set(False)
	bpy.context.view_layer.objects.active = bpy.data.objects[active_object_name]
	# If one or more objects were originally selected, restore that selection set
	if len(selected_objects) >= 1:
		# Re-select previously selected objects
		for obj in selected_objects:
			obj.select_set(True)
	
	# Done
	return {'FINISHED'}


###########################################################################
# Project settings and UI rendering classes

class vfSegmentMeshSettings(bpy.types.PropertyGroup):
	tile_count: bpy.props.IntVectorProperty(
		name="Tile Count",
		description="Number of X/Y tiles",
		subtype="XYZ",
		size=2,
		default=[4, 4],
		step=1,
		soft_min=2,
		soft_max=8,
		min=1,
		max=64)
	tile_size: bpy.props.FloatVectorProperty(
		name='Tile Size',
		description='Size of each X/Y tile',
		subtype='XYZ_LENGTH',
#		unit='LENGTH',
		size=2,
		default=(100.0, 100.0),
		step=1,
		precision=2,
		soft_min=1.0,
		soft_max=1000.0,
		min=0.0,
		max=10000.0)
	tile_segment: bpy.props.EnumProperty(
		name = 'Segmentation',
		description = 'Segment mesh by individual polygons or connected groups',
		items = [
			('POLY', 'Polygon', 'Segment mesh by individual polygons (cuts apart merged elements)'),
			('POINT', 'Average Vertex', 'Segment mesh by the vertex density of each contiguous polygon island (maintains merged elements)'),
			('BOX', 'Bounding Box', 'Segment mesh by the bounding box of each contiguous polygon island (maintains merged elements)')
#			('GROUP', 'Group', 'Segment mesh by connected groups (maintains merged elements)')
			],
		default = 'POLY')
	tile_bounds: bpy.props.BoolProperty(
		name="Outside Bounds",
		description="Include elements outside the defined grid boundaries",
		default=False,
		update=VF_SegmentMeshPreview)
	show_preview: bpy.props.BoolProperty(
		name="Show Preview",
		description="Enable preview grid mesh",
		default=False,
		update=VF_SegmentMeshPreview)

class VFTOOLS_PT_segment_mesh(bpy.types.Panel):
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = 'VF Tools'
	bl_order = 0
	bl_options = {'DEFAULT_CLOSED'}
	bl_label = "Segment Mesh"
	bl_idname = "VFTOOLS_PT_segment_mesh"
	
	@classmethod
	def poll(cls, context):
		return True
	
	def draw_header(self, context):
		try:
			layout = self.layout
		except Exception as exc:
			print(str(exc) + " | Error in VF Segment Mesh panel header")
			
	def draw(self, context):
		try:
			# Check if mesh object is selected
			if context.active_object and context.active_object.type == 'MESH' and len(context.active_object.data.polygons) > 0:
				button_enable = True
				button_title = "Create " + str(object_count) + " Segments"
				button_icon = "MESH_GRID"
			else:
				button_enable = False
				button_title = "Select Mesh"
				button_icon = "OUTLINER_DATA_MESH"
			
			# UI Layout
			layout = self.layout
			layout.use_property_decorate = False # No animation
			
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_count')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_size')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment', expand=True)
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_bounds')
			layout.prop(context.scene.vf_segment_mesh_settings, 'show_preview')
			
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_count', text = '')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_size', text = '')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment', text = '')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment', text = '', expand=True)
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_bounds', text = '')
			layout.prop(context.scene.vf_segment_mesh_settings, 'show_preview', text = '')
			
			if button_enable:
				layout.operator(VF_SegmentMesh.bl_idname, text = button_title, icon = button_icon)
			else:
				disabled = layout.row()
				disabled.active = False
				disabled.enabled = False
				disabled.operator(VF_SegmentMesh.bl_idname, text = button_title, icon = button_icon)
			
		except Exception as exc:
			print(str(exc) + " | Error in VF Segment Mesh panel")

classes = (VF_SegmentMesh, VF_SegmentMeshPreview, vfSegmentMeshSettings, VFTOOLS_PT_segment_mesh)

###########################################################################
# Addon registration functions

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.Scene.vf_segment_mesh_settings = bpy.props.PointerProperty(type = vfSegmentMeshSettings)
	
def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.vf_segment_mesh_settings
	
if __name__ == "__main__":
	register()
	