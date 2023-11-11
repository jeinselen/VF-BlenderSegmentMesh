bl_info = {
	"name": "VF Segment Mesh",
	"author": "John Einselen - Vectorform LLC",
	"version": (0, 8, 0),
	"blender": (3, 6, 0),
	"location": "Scene > VF Tools > Segment Mesh",
	"description": "Divide meshes into grid based segments",
	"warning": "inexperienced developer, use at your own risk",
	"doc_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh",
	"tracker_url": "https://github.com/jeinselenVF/VF-BlenderSegmentMesh/issues",
	"category": "3D View"}

import bpy
import bmesh
from mathutils import Vector
from mathutils import Matrix
from bpy.app.handlers import persistent

###########################################################################
# Main class

class VF_SegmentMesh(bpy.types.Operator):
	bl_idname = "object.vf_segment_mesh"
	bl_label = "Segment Mesh"
	bl_description = "Divide large meshes into grid-based components for more efficient rendering in realtime game engines"
	bl_options = {'REGISTER', 'UNDO'}
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	
	def draw(self, context):
		try:
			layout = self.layout
			layout.label(text="Blender will be unresponsive while processing, proceed?")
		except Exception as exc:
			print(str(exc) + ' | Error in VF Segment Mesh: Begin segmentation confirmation')
	
	def execute(self, context):
		# Ensure mode is set to object
		bpy.ops.object.mode_set(mode='OBJECT')
		
		# Set up local variables
		sizeX = context.scene.vf_segment_mesh_settings.tile_size[0]
		sizeY = context.scene.vf_segment_mesh_settings.tile_size[1]
		countX = context.scene.vf_segment_mesh_settings.tile_count[0]
		countY = context.scene.vf_segment_mesh_settings.tile_count[1]
		startX = sizeX * float(countX) * -0.5
		startY = sizeY * float(countY) * -0.5
		segment = context.scene.vf_segment_mesh_settings.tile_segment
		origin = context.scene.vf_segment_mesh_settings.tile_origin
		bounds = True if context.scene.vf_segment_mesh_settings.tile_bounds == "OUT" else False
		attribute_name = "island_position"
		
		# Apply all transforms (otherwise world-space calculations are going to be all off)
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
		
		# Get active object by name instead of by active reference (so the source object doesn't change during processing)
		object_name = str(context.active_object.name)
		mesh_object = bpy.data.objects[object_name]
		
		# Calculate island positions if we're not in per-polygon mode
		if segment != "POLY":
			# BMesh approach (impossibly slow on geometry over a few hundred thousand polygons)
#			obj = context.active_object
#			if obj and obj.type == 'MESH':
				# Call the function to mark polygon islands
#				vf_store_polygon_islands(obj)
			# Geometry Nodes approach (doesn't support bounding box calculation, but it works)
			mod = mesh_object.modifiers.new(name="VF-StoreIslandAttributes-TEMP", type='NODES')
			mod.node_group = store_island_attributes_node_group()
			bpy.ops.object.modifier_apply(modifier="VF-StoreIslandAttributes-TEMP")
			bpy.data.node_groups.remove(bpy.data.node_groups["VF-StoreIslandAttributes-TEMP"])
		
		# Save current 3D cursor location and pivot point
		original_cursor = context.scene.cursor.matrix
		original_pivot = context.tool_settings.transform_pivot_point
		
		# Track names of each created object
		separated_collection = []
		
		# Loop through each grid space
		for x in range(countX):
			# Define min/max for X
			min_x = startX + (x * sizeX)
			max_x = min_x + sizeX
			loc_x = (max_x + min_x) / 2
			if bounds:
				if x == 0:
					min_x = float('-inf')
				elif x == countX-1:
					max_x = float('inf')
			
			for y in range(countY):
				# Define min/max for Y
				min_y = startY + (y * sizeY)
				max_y = min_y + sizeY
				loc_y = (max_y + min_y) / 2
				if bounds:
					if y == 0:
						min_y = float('-inf')
					elif y == countY-1:
						max_y = float('inf')
				
				# Prevent out-of-range errors (seems like the attribute indices aren't updated after splitting geometry)
				mesh_object.data.update()
				# Re-get the mesh data to ensure everything is up-to-date
				mesh_data = mesh_object.data
				
				# Get attribute data if needed
				if segment == "AVERAGE":
					island_info = "island_mean"
				elif segment == "WEIGHTED":
					island_info = "island_weighted"
				else:
					island_info = False
				
				# Create tile name
				tile_name = mesh_object.name + "-Tile-" + str(x) + "-" + str(y)
				
				# Count how many polygons have been selected
				count = 0
				
				# Select polygons within the specified XYZ area
				for polygon in mesh_data.polygons:
					if island_info:
						# Get precalculated island position
						element_position = mesh_data.attributes[island_info].data[polygon.index].vector
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
					context.view_layer.objects.active = mesh_object
					mesh_object.select_set(True)
					bpy.ops.object.mode_set(mode='EDIT')
					bpy.ops.mesh.separate(type='SELECTED')
					bpy.ops.object.mode_set(mode='OBJECT')
					
					# Rename the separated object and mesh
					separated_object = context.selected_objects[1]
					separated_object.name = tile_name
					separated_mesh = separated_object.data
					separated_mesh.name = tile_name
					separated_object.select_set(False)
					separated_collection.append(tile_name)
					
					# Apply transforms, set the origin, and set the position of the separated object
					with context.temp_override(
							active_object=separated_object,
							editable_objects=[separated_object],
							object=separated_object,
							selectable_objects=[separated_object],
							selected_editable_objects=[separated_object],
							selected_objects=[separated_object]):
						
						if origin == "TILE":
							context.scene.cursor.matrix = Matrix(((1.0, 0.0, 0.0, loc_x),(0.0, 1.0, 0.0, loc_y),(-0.0, 0.0, 1.0, 0.0),(0.0, 0.0, 0.0, 1.0)))
							bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
						elif origin == "BOX":
							context.tool_settings.transform_pivot_point = "BOUNDING_BOX_CENTER"
							bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
						elif origin == "MEDIAN":
							context.tool_settings.transform_pivot_point = "MEDIAN_POINT"
							bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
						elif origin == "MASS":
							bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS')
						elif origin == "VOLUME":
							bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME')
		
		# Select all newly created segments
		for name in separated_collection:
			bpy.data.objects[name].select_set(True)
		
		# If no elements remain in the original source, remove it and set the first tile to active
		if len(mesh_object.data.vertices) == 0:
			bpy.data.meshes.remove(mesh_object.data)
			bpy.context.view_layer.objects.active = bpy.data.objects[separated_collection[0]]
		
		# Restore original 3D cursor position and pivot point
		context.scene.cursor.matrix = original_cursor
		context.tool_settings.transform_pivot_point = original_pivot
		
		# Done
		return {'FINISHED'}



# Many thanks to Brendan Parmer for making this easy https://github.com/BrendanParmer/NodeToPython
@persistent
def store_island_attributes_node_group():
	store_island_attributes= bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "VF-StoreIslandAttributes-TEMP")
	
	#initialize store_island_attributes nodes
	#store_island_attributes outputs
	#output Geometry
	store_island_attributes.outputs.new('NodeSocketGeometry', "Geometry")
	store_island_attributes.outputs[0].attribute_domain = 'POINT'
	
	
	#node Group Output
	group_output = store_island_attributes.nodes.new("NodeGroupOutput")
	
	#store_island_attributes inputs
	#input Geometry
	store_island_attributes.inputs.new('NodeSocketGeometry', "Geometry")
	store_island_attributes.inputs[0].attribute_domain = 'POINT'
	
	
	#node Group Input
	group_input = store_island_attributes.nodes.new("NodeGroupInput")
	
	#node Mesh Island
	mesh_island = store_island_attributes.nodes.new("GeometryNodeInputMeshIsland")
	
	#node Position
	position = store_island_attributes.nodes.new("GeometryNodeInputPosition")
	
	#node Face Area
	face_area = store_island_attributes.nodes.new("GeometryNodeInputMeshFaceArea")
	
	#node Accumulate Field
	accumulate_field = store_island_attributes.nodes.new("GeometryNodeAccumulateField")
	accumulate_field.data_type = 'FLOAT_VECTOR'
	accumulate_field.domain = 'POINT'
	#Value Float
	accumulate_field.inputs[1].default_value = 1.0
	#Value Int
	accumulate_field.inputs[2].default_value = 1
	
	#node Accumulate Field.001
	accumulate_field_001 = store_island_attributes.nodes.new("GeometryNodeAccumulateField")
	accumulate_field_001.data_type = 'INT'
	accumulate_field_001.domain = 'POINT'
	#Value Vector
	accumulate_field_001.inputs[0].default_value = (1.0, 1.0, 1.0)
	#Value Float
	accumulate_field_001.inputs[1].default_value = 1.0
	#Value Int
	accumulate_field_001.inputs[2].default_value = 1
	
	#node Accumulate Field.002
	accumulate_field_002 = store_island_attributes.nodes.new("GeometryNodeAccumulateField")
	accumulate_field_002.data_type = 'FLOAT_VECTOR'
	accumulate_field_002.domain = 'FACE'
	#Value Float
	accumulate_field_002.inputs[1].default_value = 1.0
	#Value Int
	accumulate_field_002.inputs[2].default_value = 1
	
	#node Accumulate Field.003
	accumulate_field_003 = store_island_attributes.nodes.new("GeometryNodeAccumulateField")
	accumulate_field_003.data_type = 'FLOAT'
	accumulate_field_003.domain = 'FACE'
	#Value Vector
	accumulate_field_003.inputs[0].default_value = (1.0, 1.0, 1.0)
	#Value Int
	accumulate_field_003.inputs[2].default_value = 1
	
	#node Vector Math
	vector_math = store_island_attributes.nodes.new("ShaderNodeVectorMath")
	vector_math.operation = 'DIVIDE'
	#Vector_002
	vector_math.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math.inputs[3].default_value = 1.0
	
	#node Vector Math.001
	vector_math_001 = store_island_attributes.nodes.new("ShaderNodeVectorMath")
	vector_math_001.operation = 'SCALE'
	#Vector_001
	vector_math_001.inputs[1].default_value = (0.0, 0.0, 0.0)
	#Vector_002
	vector_math_001.inputs[2].default_value = (0.0, 0.0, 0.0)
	
	#node Vector Math.002
	vector_math_002 = store_island_attributes.nodes.new("ShaderNodeVectorMath")
	vector_math_002.operation = 'DIVIDE'
	#Vector_002
	vector_math_002.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Scale
	vector_math_002.inputs[3].default_value = 1.0
	
	#node Store Named Attribute
	store_named_attribute = store_island_attributes.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute.data_type = 'INT'
	store_named_attribute.domain = 'FACE'
	#Selection
	store_named_attribute.inputs[1].default_value = True
	#Name
	store_named_attribute.inputs[2].default_value = "island_index"
	#Value_Vector
	store_named_attribute.inputs[3].default_value = (0.0, 0.0, 0.0)
	#Value_Float
	store_named_attribute.inputs[4].default_value = 0.0
	#Value_Color
	store_named_attribute.inputs[5].default_value = (0.0, 0.0, 0.0, 0.0)
	#Value_Bool
	store_named_attribute.inputs[6].default_value = False
	
	#node Store Named Attribute.002
	store_named_attribute_002 = store_island_attributes.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute_002.data_type = 'FLOAT_VECTOR'
	store_named_attribute_002.domain = 'FACE'
	#Selection
	store_named_attribute_002.inputs[1].default_value = True
	#Name
	store_named_attribute_002.inputs[2].default_value = "island_mean"
	#Value_Float
	store_named_attribute_002.inputs[4].default_value = 0.0
	#Value_Color
	store_named_attribute_002.inputs[5].default_value = (0.0, 0.0, 0.0, 0.0)
	#Value_Bool
	store_named_attribute_002.inputs[6].default_value = False
	#Value_Int
	store_named_attribute_002.inputs[7].default_value = 0
	
	#node Store Named Attribute.003
	store_named_attribute_003 = store_island_attributes.nodes.new("GeometryNodeStoreNamedAttribute")
	store_named_attribute_003.data_type = 'FLOAT_VECTOR'
	store_named_attribute_003.domain = 'FACE'
	#Selection
	store_named_attribute_003.inputs[1].default_value = True
	#Name
	store_named_attribute_003.inputs[2].default_value = "island_weighted"
	#Value_Float
	store_named_attribute_003.inputs[4].default_value = 0.0
	#Value_Color
	store_named_attribute_003.inputs[5].default_value = (0.0, 0.0, 0.0, 0.0)
	#Value_Bool
	store_named_attribute_003.inputs[6].default_value = False
	#Value_Int
	store_named_attribute_003.inputs[7].default_value = 0
	
	
	#Set locations
	group_output.location = (0.0, 0.0)
	group_input.location = (-720.0, 0.0)
	mesh_island.location = (-720.0, -100.0)
	position.location = (-900.0, -220.0)
	face_area.location = (-1080.0, -720.0)
	accumulate_field.location = (-720.0, -220.0)
	accumulate_field_001.location = (-720.0, -440.0)
	accumulate_field_002.location = (-720.0, -660.0)
	accumulate_field_003.location = (-720.0, -880.0)
	vector_math.location = (-540.0, -220.0)
	vector_math_001.location = (-900.0, -660.0)
	vector_math_002.location = (-540.0, -660.0)
	store_named_attribute.location = (-540.0, 0.0)
	store_named_attribute_002.location = (-360.0, 0.0)
	store_named_attribute_003.location = (-180.0, 0.0)
	
	#Set dimensions
	group_output.width, group_output.height = 140.0, 100.0
	group_input.width, group_input.height = 140.0, 100.0
	mesh_island.width, mesh_island.height = 140.0, 100.0
	position.width, position.height = 140.0, 100.0
	face_area.width, face_area.height = 140.0, 100.0
	accumulate_field.width, accumulate_field.height = 140.0, 100.0
	accumulate_field_001.width, accumulate_field_001.height = 140.0, 100.0
	accumulate_field_002.width, accumulate_field_002.height = 140.0, 100.0
	accumulate_field_003.width, accumulate_field_003.height = 140.0, 100.0
	vector_math.width, vector_math.height = 140.0, 100.0
	vector_math_001.width, vector_math_001.height = 140.0, 100.0
	vector_math_002.width, vector_math_002.height = 140.0, 100.0
	store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
	store_named_attribute_002.width, store_named_attribute_002.height = 140.0, 100.0
	store_named_attribute_003.width, store_named_attribute_003.height = 140.0, 100.0
	
	#initialize store_island_attributes links
	#store_named_attribute_003.Geometry -> group_output.Geometry
	store_island_attributes.links.new(store_named_attribute_003.outputs[0], group_output.inputs[0])
	#face_area.Area -> accumulate_field_003.Value
	store_island_attributes.links.new(face_area.outputs[0], accumulate_field_003.inputs[1])
	#vector_math_001.Vector -> accumulate_field_002.Value
	store_island_attributes.links.new(vector_math_001.outputs[0], accumulate_field_002.inputs[0])
	#accumulate_field_002.Total -> vector_math_002.Vector
	store_island_attributes.links.new(accumulate_field_002.outputs[6], vector_math_002.inputs[0])
	#accumulate_field_003.Total -> vector_math_002.Vector
	store_island_attributes.links.new(accumulate_field_003.outputs[7], vector_math_002.inputs[1])
	#accumulate_field.Total -> vector_math.Vector
	store_island_attributes.links.new(accumulate_field.outputs[6], vector_math.inputs[0])
	#accumulate_field_001.Total -> vector_math.Vector
	store_island_attributes.links.new(accumulate_field_001.outputs[8], vector_math.inputs[1])
	#face_area.Area -> vector_math_001.Scale
	store_island_attributes.links.new(face_area.outputs[0], vector_math_001.inputs[3])
	#position.Position -> accumulate_field.Value
	store_island_attributes.links.new(position.outputs[0], accumulate_field.inputs[0])
	#group_input.Geometry -> store_named_attribute.Geometry
	store_island_attributes.links.new(group_input.outputs[0], store_named_attribute.inputs[0])
	#store_named_attribute.Geometry -> store_named_attribute_002.Geometry
	store_island_attributes.links.new(store_named_attribute.outputs[0], store_named_attribute_002.inputs[0])
	#store_named_attribute_002.Geometry -> store_named_attribute_003.Geometry
	store_island_attributes.links.new(store_named_attribute_002.outputs[0], store_named_attribute_003.inputs[0])
	#mesh_island.Island Index -> store_named_attribute.Value
	store_island_attributes.links.new(mesh_island.outputs[0], store_named_attribute.inputs[7])
	#vector_math.Vector -> store_named_attribute_002.Value
	store_island_attributes.links.new(vector_math.outputs[0], store_named_attribute_002.inputs[3])
	#vector_math_002.Vector -> store_named_attribute_003.Value
	store_island_attributes.links.new(vector_math_002.outputs[0], store_named_attribute_003.inputs[3])
	#mesh_island.Island Index -> accumulate_field.Group ID
	store_island_attributes.links.new(mesh_island.outputs[0], accumulate_field.inputs[3])
	#mesh_island.Island Index -> accumulate_field_001.Group ID
	store_island_attributes.links.new(mesh_island.outputs[0], accumulate_field_001.inputs[3])
	#mesh_island.Island Index -> accumulate_field_002.Group ID
	store_island_attributes.links.new(mesh_island.outputs[0], accumulate_field_002.inputs[3])
	#mesh_island.Island Index -> accumulate_field_003.Group ID
	store_island_attributes.links.new(mesh_island.outputs[0], accumulate_field_003.inputs[3])
	#position.Position -> vector_math_001.Vector
	store_island_attributes.links.new(position.outputs[0], vector_math_001.inputs[0])
	return store_island_attributes



@persistent
def vf_store_polygon_islands(obj):
	mesh = obj.data
	
	# Create a BMesh object from the mesh
	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.faces.ensure_lookup_table()
	bm.verts.ensure_lookup_table()
	
	# Get or create custom face attributes
	if 'island_index' in bm.faces.layers.int:
		island_index = bm.faces.layers.int['island_index']
	else:
		island_index = bm.faces.layers.int.new('island_index')
	
	if 'island_box' in bm.faces.layers.float_vector:
		island_box = bm.faces.layers.float_vector['island_box']
	else:
		island_box = bm.faces.layers.float_vector.new('island_box')
	
	if 'island_poly' in bm.faces.layers.float_vector:
		island_poly = bm.faces.layers.float_vector['island_poly']
	else:
		island_poly = bm.faces.layers.float_vector.new('island_poly')
	
	if 'island_median' in bm.faces.layers.float_vector:
		island_median = bm.faces.layers.float_vector['island_median']
	else:
		island_median = bm.faces.layers.float_vector.new('island_median')

	if 'island_weighted' in bm.faces.layers.float_vector:
		island_weighted = bm.faces.layers.float_vector['island_weighted']
	else:
		island_weighted = bm.faces.layers.float_vector.new('island_weighted')
	
	# Initialise polygon tags before traversal
	for poly in bm.faces:
		poly.tag = False
	
	# Track current island index
	track_index = 0
	
	# Iterate through all polygons in the BMesh
	for poly in bm.faces:
		if not poly.tag:
			# Start a new island
			island_polygons = set()
			island_vertices = set()
			stack = [poly]
			
			# Perform depth-first search to find connected polygons
			while stack:
				current_poly = stack.pop()
				island_polygons.add(current_poly.index)
				current_poly.tag = True
				
				# Find adjacent polygons by checking neighboring edges
#				for edge in current_poly.edges:
#					for adjacent_poly in edge.link_faces:
#						if not adjacent_poly.tag:
#							stack.append(adjacent_poly)
#							adjacent_poly.tag = True
				
				# Find adjacent polygons by checking connected vertices
				for vert in current_poly.verts:
					for connected_poly in vert.link_faces:
						if not connected_poly.tag:
							stack.append(connected_poly)
							connected_poly.tag = True
			
			# Create island positional data
			# Get current island bounding box centre point
			position_box_min = Vector((float("inf"), float("inf"), float("inf")))
			position_box_max = Vector((float("-inf"), float("-inf"), float("-inf")))
			for p in island_polygons:
				for v in bm.faces[p].verts:
					vertex_position = bm.verts[v.index].co
					position_box_min.x = min(position_box_min.x, vertex_position.x)
					position_box_min.y = min(position_box_min.y, vertex_position.y)
					position_box_min.z = min(position_box_min.z, vertex_position.z)
					position_box_max.x = max(position_box_max.x, vertex_position.x)
					position_box_max.y = max(position_box_max.y, vertex_position.y)
					position_box_max.z = max(position_box_max.z, vertex_position.z)
			
			# Get current island weighted polygon position average
			position_poly = sum((f.calc_center_bounds() for f in bm.faces if f.index in island_polygons), Vector())/(len(island_polygons))
			
			# Get current island weighted polygon position average
			position_median = sum((f.calc_center_median() for f in bm.faces if f.index in island_polygons), Vector())/(len(island_polygons))
			
			# Get current island weighted polygon position average
			position_weighted = sum((f.calc_center_median_weighted() for f in bm.faces if f.index in island_polygons), Vector())/(len(island_polygons))
			
			# Assign island data to the polygons
			for island_poly_index in island_polygons:
				bm.faces[island_poly_index][island_index] = track_index
				bm.faces[island_poly_index][island_box] = (position_box_max + position_box_min) / 2
				bm.faces[island_poly_index][island_poly] = position_poly
				bm.faces[island_poly_index][island_median] = position_median
				bm.faces[island_poly_index][island_weighted] = position_weighted
			
			track_index += 1
	
	# Reset polygon tags before saving back to the mesh
	for poly in bm.faces:
		poly.tag = False
	
	# Finish up, write the bmesh back to the mesh
	bm.to_mesh(mesh)
	bm.free() # free and prevent further access
	obj.data.update() # This ensures the viewport updates
		
	# Done
	return None



@persistent
def vf_segment_mesh_preview(self, context):
	mesh_name = "VF-SegmentMeshPreview-TEMP"
	
	# Remove existing mesh data block (and associated object) if it exists
	if mesh_name in bpy.data.meshes:
		bpy.data.meshes.remove(bpy.data.meshes[mesh_name])
	
	# Stop now if the preview mesh is disabled
	if not context.scene.vf_segment_mesh_settings.show_preview:
		# Done
		return None
	
	# Set up local variables
	sizeX = context.scene.vf_segment_mesh_settings.tile_size[0]
	sizeY = context.scene.vf_segment_mesh_settings.tile_size[1]
	countX = context.scene.vf_segment_mesh_settings.tile_count[0]
	countY = context.scene.vf_segment_mesh_settings.tile_count[1]
	
	# Save the current object selection
	active_object_name = str(context.active_object.name) if context.active_object else False
	selected_objects = [obj for obj in context.selected_objects]
	
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
	context.active_object.scale = (sizeX * countX, sizeY * countY, 1.0)
	bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
	
	# Convert to wireframe and disable for rendering
	bpy.ops.object.modifier_add(type='WIREFRAME')
	context.object.modifiers["Wireframe"].thickness = float(max(sizeX, sizeY)) * 0.05
#	bpy.ops.object.modifier_apply()
	context.object.hide_render = True
		
	# Rename object and mesh data block
	context.active_object.name = mesh_name
	context.active_object.data.name = mesh_name
	
	# Reset selection
	context.active_object.select_set(False)
	if active_object_name:
		context.view_layer.objects.active = bpy.data.objects[active_object_name]
	# If one or more objects were originally selected, restore that selection set
	if len(selected_objects) >= 1:
		# Re-select previously selected objects
		for obj in selected_objects:
			obj.select_set(True)
	
	# Done
	return None



###########################################################################
# Project settings and UI rendering classes

class vfSegmentMeshSettings(bpy.types.PropertyGroup):
	tile_size: bpy.props.FloatVectorProperty(
		name='Size',
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
		update=vf_segment_mesh_preview)
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
		update=vf_segment_mesh_preview)
	tile_bounds: bpy.props.EnumProperty(
		name = 'Include',
		description = 'Specify if geometry outside the tile area will be included in the nearest tile or not',
		items = [
			('IN', 'Only Inside', 'Limits tile content to only the elements that fall within each tile boundary'),
			('OUT', 'Extend Edges', 'Includes content beyond the edges of the tile array, ensuring nothing is left out')
			],
		default = 'OUT')
	tile_segment: bpy.props.EnumProperty(
		name = 'Segment',
		description = 'Segment mesh by individual polygons or connected mesh islands',
		items = [
			('POLY', 'Per Polygon', 'Segment mesh by individual polygons (cuts apart merged elements)'),
			('AVERAGE', 'Island Average', 'Segment mesh based on the average vertex positions of each contiguous island (maintains merged elements)'),
			('WEIGHTED', 'Island Weighted', 'Segment mesh based on the weighted polygon positions of each contiguous island (maintains merged elements)')
			],
		default = 'WEIGHTED')
	tile_origin: bpy.props.EnumProperty(
		name = 'Origin',
		description = 'Choose the desired origin for each tile',
		items = [
			# Source is a bit of a problem, since we need to apply all transforms before processing world-space tiles; the original orientation of the object needs to be saved first, which isn't implemented yet
#			('SOURCE', 'Source', 'Maintains the origin from the source object (not ideal in cases where culling algorithms take origin into account)'),
			('TILE', 'Tile', 'Set each tile origin to the centre of the tile space (best for predictable placement but may not be as ideal for transparency sorting in some cases)'),
			('BOX', 'Bounding Box', 'Set each tile origin to the geometry bounding box'),
			('MEDIAN', 'Median', 'Set each tile origin to the geometry median'),
			('MASS', 'Mass', 'Set each tile origin to the geometry mass'),
			('VOLUME', 'Volume', 'Set each tile origin to the geometry volume')
			],
		default = 'TILE')
	show_preview: bpy.props.BoolProperty(
		name="Preview",
		description="Enable preview grid mesh",
		default=False,
		update=vf_segment_mesh_preview)

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
			col = layout.column(align=True)
			col.prop(context.scene.vf_segment_mesh_settings, 'tile_bounds')
			col.prop(context.scene.vf_segment_mesh_settings, 'tile_segment')
			col.prop(context.scene.vf_segment_mesh_settings, 'tile_origin')
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
	