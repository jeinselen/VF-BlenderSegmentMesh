bl_info = {
	"name": "VF Segment Mesh",
	"author": "John Einselen - Vectorform LLC",
	"version": (0, 3, 0),
	"blender": (3, 6, 0),
	"location": "Scene > VF Tools > Segment Mesh",
	"description": "Divide meshes into grid based segments",
	"warning": "inexperienced developer, use at your own risk",
	"doc_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh",
	"tracker_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh/issues",
	"category": "3D View"}

import bpy
from mathutils import Vector
#from bpy.app.handlers import persistent

###########################################################################
# Main class

class VF_SegmentMesh(bpy.types.Operator):
	bl_idname = "object.vf_segment_mesh"
	bl_label = "Segment Mesh"
	bl_description = "Divide large meshes into grid-based components for more efficient rendering in realtime game engines"
#	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		# Set up local variables
		sizeX = bpy.context.scene.vf_segment_mesh_settings.tile_size[0]
		sizeY = bpy.context.scene.vf_segment_mesh_settings.tile_size[1]
		countX = bpy.context.scene.vf_segment_mesh_settings.tile_count[0]
		countY = bpy.context.scene.vf_segment_mesh_settings.tile_count[1]
		startX = sizeX * float(countX) * -0.5
		startY = sizeY * float(countY) * -0.5
		group = True if bpy.context.scene.vf_segment_mesh_settings.tile_segment == "GROUP" else False
		bounds = True if bpy.context.scene.vf_segment_mesh_settings.tile_bounds == "INCLUDE" else False
		
		# Get active object by name (so the source object doesn't change during processing)
		object_name = bpy.context.active_object.name
		mesh_object = bpy.data.objects[object_name]
		mesh = mesh_object.data
		
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

class VF_SegmentMeshPreview(bpy.types.Operator):
	bl_idname = "object.vf_segment_mesh_preview"
	bl_label = "Segment Mesh"
	bl_description = "Divide large meshes into grid-based components for more efficient rendering in realtime game engines"
#	bl_options = {'REGISTER', 'UNDO'}
	
	remove: bpy.props.BoolProperty()
	
	def execute(self, context):
		# Remove existing mesh data block (and associated object) if it exists
		if mesh_name in bpy.data.meshes:
			mesh = bpy.data.meshes[mesh_name]
			bpy.data.meshes.remove(mesh)
			bpy.data.meshes.remove(bpy.data.meshes[mesh_name])
		
		# Stop now if we're removing the preview mesh
		if self.remove:
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
			('GROUP', 'Group', 'Segment mesh by connected groups (maintains merged elements)')
			],
		default = 'POLY')
	tile_bounds: bpy.props.EnumProperty(
		name = 'Boundaries',
		description = 'Exclude or include geometry beyond the boundaries of the defined grid',
		items = [
			('EXCLUDE', 'Exclude', 'Exclude elements outside the defined grid boundaries'),
			('INCLUDE', 'Include', 'Include elements outside the defined grid boundaries')
			],
		default = 'INCLUDE')

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
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment', expand=True)
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_bounds', expand=True)
			
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_count', text = '')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_size', text = '')
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_segment', text = '', expand=True)
			layout.prop(context.scene.vf_segment_mesh_settings, 'tile_bounds', text = '', expand=True)
			
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
	