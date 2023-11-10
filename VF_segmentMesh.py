bl_info = {
	"name": "VF Segment Mesh",
	"author": "John Einselen - Vectorform LLC",
	"version": (0, 5, 0),
	"blender": (3, 6, 0),
	"location": "Scene > VF Tools > Segment Mesh",
	"description": "Divide meshes into grid based segments",
	"warning": "inexperienced developer, use at your own risk",
	"doc_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh",
	"tracker_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh/issues",
	"category": "3D View"}

import bpy
from mathutils import Vector
import bmesh
from bpy.app.handlers import persistent

###########################################################################
# Main class

class VF_SegmentMesh(bpy.types.Operator):
	bl_idname = "object.vf_segment_mesh"
	bl_label = "Segment Mesh"
	bl_description = "Divide large meshes into grid-based components for more efficient rendering in realtime game engines"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		# Set up local variables
		sizeX = bpy.context.scene.vf_segment_mesh_settings.tile_size[0]
		sizeY = bpy.context.scene.vf_segment_mesh_settings.tile_size[1]
		countX = bpy.context.scene.vf_segment_mesh_settings.tile_count[0]
		countY = bpy.context.scene.vf_segment_mesh_settings.tile_count[1]
		startX = sizeX * float(countX) * -0.5
		startY = sizeY * float(countY) * -0.5
		group = True if bpy.context.scene.vf_segment_mesh_settings.tile_segment != "POLY" else False
		vert = True if bpy.context.scene.vf_segment_mesh_settings.tile_segment == "VERT" else False
		bounds = bpy.context.scene.vf_segment_mesh_settings.tile_bounds
		attribute_name = "island_position"
		
		# Get active object by name (so the source object doesn't change during processing)
		# This seems VERY silly, I just can't remember how to create a reference to the active object without it changing when the active object changes?
		object_name = str(bpy.context.active_object.name)
		mesh_object = bpy.data.objects[object_name]
		mesh_data = mesh_object.data
		
		# Calculate island positions if we're not in per-polygon mode
		if group:
			# Convert the mesh to a BMesh for easier manipulation
			bm = bmesh.new()
			bm.from_mesh(mesh_data)
			
			# Create a custom vector polygon attribute to store the bounding box centers
			attr = bm.faces.layers.float_vector.new(attribute_name)
			
			# Set vectors to infinity so we can track which elements have been processed
			unset_value = Vector((float('-inf'), float('-inf'), float('-inf')))
			for face in bm.faces:
				face[attr] = unset_value
				face.select_set(False)
			
			# Iterate through polygons to find mesh islands
			for face in bm.faces:
				# Check if the custom attribute already exists on the current polygon
				if face[attr] != unset_value:
#					print("attr exists")
					# If the attribute exists, skip to the next polygon
					continue
				
				# Select the current face
				face.select_set(True)
				
				# Expand the selection to linked polygons
#				bpy.ops.mesh.select_linked(delimit=set())
				# BUT THIS IS FOR THE ORIGINAL MESH, NOT BMESH!
				
				bmesh.ops.region_extend(bm, use_faces=True, use_face_step=False)
				
				# Get the selected polygons
				selected_polygons = [poly for poly in bm.faces if poly.select]
				
				print("selected_polygons: " + len(selected_polygons))
				
				# Corrected?
#				selected_polygons = [poly for poly in bpy.context.active_object.data.polygons if poly.select]
				
#				print(dir(bm.faces))
				
				# Calculate selected mesh island position, either average vertex or bounding box
				if vert:
					# Calculate average vertex center
					vertices = [v.co for poly in selected_polygons for v in poly.verts]
					bounding_box_center = sum(vertices, Vector()) / len(vertices)
				else:
					# Calculate bounding box minimmum and maximum extents
					min_coords = Vector((float('inf'), float('inf'), float('inf')))
					max_coords = Vector((-float('inf'), -float('inf'), -float('inf')))
					for poly in selected_polygons:
#						print(dir(poly))
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
			
			# Update the mesh with the changes from the BMesh
			bm.to_mesh(mesh_data)
			bm.free()
		
#			if attribute_name in mesh_data.polygons.layers.float_vector:
			if attribute_name in mesh_data.attributes:
				attribute_layer = mesh_data.attributes[attribute_name]
			else:
				attribute_layer = False
				print("VF Segment Mesh - failed to calculate and store mesh island positions")
		
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
				
				# Select polygons within the specified XYZ area
				for polygon in mesh_data.polygons:
					if group and attribute_layer:
						# Get precalculated island position
						element_position = attribute_layer.data[polygon.index].vector
					else:
						# Find average vertex location of individual polygon
						element_position = Vector((0, 0, 0))
						for vertice_index in polygon.vertices:
							element_position += mesh_data.vertices[vertice_index].co
						element_position /= len(polygon.vertices)
					
					# Check element position against min/max
					if min_x <= element_position.x <= max_x and min_y <= element_position.y <= max_y:
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

@persistent
def VF_SegmentMeshPreview(self, context):
	mesh_name = "VF-SegmentMeshPreview-TEMP"
#				vf_segment_mesh_preview_temp
	
	# Remove existing mesh data block (and associated object) if it exists
	if mesh_name in bpy.data.meshes:
#	if bpy.data.meshes.get(mesh_name):
		mesh = bpy.data.meshes[mesh_name]
		bpy.data.meshes.remove(mesh)
		bpy.data.meshes.remove(bpy.data.meshes[mesh_name])
	
	# Stop now if the preview mesh is disabled
	if not bpy.context.scene.vf_segment_mesh_settings.show_preview:
		# Done
#		return {'FINISHED'}
		return None
	
	# Set up local variables
	sizeX = bpy.context.scene.vf_segment_mesh_settings.tile_size[0]
	sizeY = bpy.context.scene.vf_segment_mesh_settings.tile_size[1]
	countX = bpy.context.scene.vf_segment_mesh_settings.tile_count[0]
	countY = bpy.context.scene.vf_segment_mesh_settings.tile_count[1]
	
	# Save the current object selection
	active_object_name = str(bpy.context.active_object.name) if bpy.context.active_object else False
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
	
	# Convert to wireframe and disable for rendering
	bpy.ops.object.modifier_add(type='WIREFRAME')
	bpy.context.object.modifiers["Wireframe"].thickness = float(max(sizeX, sizeY)) * 0.05
#	bpy.ops.object.modifier_apply()
	bpy.context.object.hide_render = True
		
	# Rename object and mesh data block
	bpy.context.active_object.name = mesh_name
	bpy.context.active_object.data.name = mesh_name
	
	# Reset selection
	bpy.context.active_object.select_set(False)
	if active_object_name:
		bpy.context.view_layer.objects.active = bpy.data.objects[active_object_name]
	# If one or more objects were originally selected, restore that selection set
	if len(selected_objects) >= 1:
		# Re-select previously selected objects
		for obj in selected_objects:
			obj.select_set(True)
	
	# Done
#	return {'FINISHED'}
	return None


###########################################################################
# Project settings and UI rendering classes

class vfSegmentMeshSettings(bpy.types.PropertyGroup):
	tile_size: bpy.props.FloatVectorProperty(
		name='Tile',
		description='Size of each X/Y tile',
		subtype='XYZ_LENGTH',
		size=2,
		default=(100.0, 100.0),
		step=1,
		precision=2,
		soft_min=1.0,
		soft_max=1000.0,
		min=0.0,
		max=10000.0,
		update=VF_SegmentMeshPreview)
	tile_count: bpy.props.IntVectorProperty(
		name="Count",
		description="Number of X/Y tiles",
		subtype="XYZ",
		size=2,
		default=[4, 4],
		step=1,
		soft_min=2,
		soft_max=8,
		min=1,
		max=64,
		update=VF_SegmentMeshPreview)
	tile_segment: bpy.props.EnumProperty(
		name = 'Segment',
		description = 'Segment mesh by individual polygons or connected groups',
		items = [
			('POLY', 'Per Polygon', 'Segment mesh by individual polygons (cuts apart merged elements)'),
			('VERT', 'Average Vertex', 'Segment mesh based on the vertex density of each contiguous polygon island (maintains merged elements)'),
			('BOX', 'Bounding Box', 'Segment mesh based on the bounding box of each contiguous polygon island (maintains merged elements)')
#			('GROUP', 'Group', 'Segment mesh by connected groups (maintains merged elements)')
			],
		default = 'POLY')
	tile_bounds: bpy.props.BoolProperty(
		name="Include Edges",
		description="Include elements outside the defined boundary edges",
		default=False,
		update=VF_SegmentMeshPreview)
	show_preview: bpy.props.BoolProperty(
		name="Preview",
		description="Enable preview grid mesh",
		default=False,
		update=VF_SegmentMeshPreview)

class VFTOOLS_PT_segment_mesh(bpy.types.Panel):
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = 'VF Tools'
	bl_order = 20
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
				button_title = "Create " + str(context.scene.vf_segment_mesh_settings.tile_count[0] * context.scene.vf_segment_mesh_settings.tile_count[1]) + " Segments"
				button_icon = "MESH_GRID"
			else:
				button_enable = False
				button_title = "Select Mesh"
				button_icon = "OUTLINER_DATA_MESH"
			
			# UI Layout
			layout = self.layout
			layout.use_property_decorate = False # No animation
			layout.use_property_split = True
			
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_size')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_count')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_bounds')
			layout.prop(context.scene.vf_segment_mesh_settings, 'show_preview')
						
			if button_enable:
				layout.operator(VF_SegmentMesh.bl_idname, text = button_title, icon = button_icon)
			else:
				disabled = layout.row()
				disabled.active = False
				disabled.enabled = False
				disabled.operator(VF_SegmentMesh.bl_idname, text = button_title, icon = button_icon)
			
		except Exception as exc:
			print(str(exc) + " | Error in VF Segment Mesh panel")

classes = (VF_SegmentMesh, vfSegmentMeshSettings, VFTOOLS_PT_segment_mesh)

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
	