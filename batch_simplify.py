bl_info = {
    "name": "Blender Batch Simplifier",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > FBX Processor",
    "description": "批次處理FBX檔案：填洞和QEM減面",
    "category": "Import-Export",
}

import bpy
import os
from pathlib import Path
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Panel, Operator, PropertyGroup


class SimplifierProperties(PropertyGroup):
    """屬性群組，儲存所有參數"""
    
    input_directory: StringProperty(
        name="Input Directory",
        description="選擇包含FBX檔案的輸入資料夾",
        default="",
        subtype='DIR_PATH'
    ) # type: ignore
    
    recursive_process: BoolProperty(
        name="Recursive Process",
        description="遞迴處理所有子資料夾",
        default=False
    ) # type: ignore
    
    output_directory: StringProperty(
        name="Output Directory",
        description="選擇輸出資料夾",
        default="",
        subtype='DIR_PATH'
    ) # type: ignore
    
    fill_hole: BoolProperty(
        name="Fill Holes",
        description="填補模型的洞",
        default=True
    ) # type: ignore
    
    use_qem: BoolProperty(
        name="Use QEM Decimation",
        description="使用QEM減面",
        default=True
    ) # type: ignore
    
    qem_ratio: FloatProperty(
        name="QEM Ratio",
        description="減面比例 (0.0 - 1.0)",
        default=0.5,
        min=0.0,
        max=1.0,
        precision=3
    ) # type: ignore


class BATCH_OT_FBXSimplifiy(Operator):
    """批次處理FBX檔案的操作器"""
    bl_idname = "batch.batch_fbx_simplify"
    bl_label = "Process FBX Files"
    bl_description = "批次處理所有FBX檔案"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props : SimplifierProperties = context.scene.simplifier_props
        
        # 驗證輸入
        if not props.input_directory or not os.path.isdir(props.input_directory):
            self.report({'ERROR'}, "請選擇有效的輸入資料夾")
            return {'CANCELLED'}
        
        if not props.output_directory or not os.path.isdir(props.output_directory):
            self.report({'ERROR'}, "請選擇有效的輸出資料夾")
            return {'CANCELLED'}
        
        if props.input_directory == props.output_directory:
            self.report({'ERROR'}, "輸入和輸出資料夾不能一樣")
            return {'CANCELLED'}
        
        # 收集所有需要處理的FBX檔案
        fbx_files = self.collect_fbx_files(props.input_directory, props.recursive_process)
        
        if not fbx_files:
            self.report({'WARNING'}, "在輸入資料夾中沒有找到FBX檔案")
            return {'CANCELLED'}
        
        # 處理每個FBX檔案
        processed_count = 0
        for fbx_path, relative_path in fbx_files:
            try:
                self.process_fbx_file(fbx_path, relative_path, props)
                processed_count += 1
            except Exception as e:
                self.report({'WARNING'}, f"處理 {fbx_path} 時發生錯誤: {str(e)}")
        
        # 清理
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.ops.outliner.orphans_purge()

        self.report({'INFO'}, f"成功處理 {processed_count}/{len(fbx_files)} 個檔案")
        return {'FINISHED'}
    
    def collect_fbx_files(self, input_dir: str, recursive: bool):
        """收集所有FBX檔案 [(絕對路徑, 相對於input_dir的路徑), ...] """
        fbx_files = []
        input_path = Path(input_dir)
        
        if recursive:
            # 遞迴搜尋所有FBX檔案
            for fbx_file in input_path.rglob("*.fbx"):
                relative_path = fbx_file.relative_to(input_path)
                fbx_files.append((str(fbx_file), str(relative_path)))
        else:
            # 只搜尋當前目錄
            for fbx_file in input_path.glob("*.fbx"):
                fbx_files.append((str(fbx_file), fbx_file.name))
        
        return fbx_files
    
    def process_fbx_file(self, fbx_path: str, relative_path: str, props: SimplifierProperties):
        """處理單個FBX檔案"""
        # 清空場景
        for obj in bpy.context.scene.objects:
            bpy.data.objects.remove(obj)
        
        # 匯入FBX
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        
        # 處理所有匯入的網格物件
        mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        
        for obj in mesh_objects:
            # 選擇並設為活動物件
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            
            # 進入編輯模式
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            
            # 填洞
            if props.fill_hole:
                bpy.ops.mesh.select_mode(type='EDGE')
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.mesh.select_non_manifold(extend=False, use_wire=False, 
                                                 use_boundary=True, use_multi_face=False,
                                                 use_non_contiguous=False, use_verts=False)
                bpy.ops.mesh.edge_face_add()
            
            # QEM減面
            if props.use_qem:
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.decimate(ratio=props.qem_ratio, 
                                     use_vertex_group=False,
                                     vertex_group_factor=1.0,
                                     invert_vertex_group=False,
                                     use_symmetry=False,
                                     symmetry_axis='Y')
            
            # 返回物件模式
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # 準備輸出路徑
        output_path = Path(props.output_directory)
        relative_dir = Path(relative_path).parent
        
        # 如果是遞迴處理，建立對應的子資料夾
        if props.recursive_process and str(relative_dir) != '.':
            output_subdir = output_path / relative_dir
            output_subdir.mkdir(parents=True, exist_ok=True)
            output_file = output_subdir / Path(relative_path).name
        else:
            output_file = output_path / Path(relative_path).name
        
        # 匯出FBX
        bpy.ops.export_scene.fbx(
            filepath=str(output_file),
            use_selection=False,
            global_scale=1.0,
            apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_NONE',
            bake_space_transform=False,
            object_types={'MESH'},
            use_mesh_modifiers=True,
            mesh_smooth_type='OFF',
            use_mesh_edges=False,
            use_tspace=False,
            use_custom_props=False,
            add_leaf_bones=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            use_armature_deform_only=False,
            armature_nodetype='NULL',
            bake_anim=False,
            path_mode='AUTO',
            embed_textures=False,
            batch_mode='OFF',
            axis_forward='-Z',
            axis_up='Y'
        )


class BATCH_PT_MainPanel(Panel):
    """FBX處理器面板"""
    bl_label = "Batch Processor"
    bl_idname = "BATCH_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Processor"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.simplifier_props
        
        # 輸入資料夾
        box = layout.box()
        box.label(text="輸入設定:", icon='IMPORT')
        box.prop(props, "input_directory")
        box.prop(props, "recursive_process")
        
        # 輸出資料夾
        box = layout.box()
        box.label(text="輸出設定:", icon='EXPORT')
        box.prop(props, "output_directory")
        
        # 處理選項
        box = layout.box()
        box.label(text="處理選項:", icon='MODIFIER')
        box.prop(props, "fill_hole")
        box.prop(props, "use_qem")
        
        # QEM比例（僅當啟用QEM時顯示）
        if props.use_qem:
            box.prop(props, "qem_ratio", slider=True)
        
        # 執行按鈕
        layout.separator()
        row = layout.row()
        row.scale_y = 2.0
        row.operator("batch.batch_fbx_simplify", icon='PLAY')


# 註冊類別
classes = (
    SimplifierProperties,
    BATCH_OT_FBXSimplifiy,
    BATCH_PT_MainPanel,
)


def register():
    """註冊Addon"""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.simplifier_props = bpy.props.PointerProperty(
        type=SimplifierProperties
    )


def unregister():
    """取消註冊Addon"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.simplifier_props


if __name__ == "__main__":
    register()
