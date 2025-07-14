import streamlit as st
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

DEFAULT_PRESETS_FILE = "presets.json"

def get_presets_directory() -> str:
    """Get the presets directory path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, '..', 'data', 'filter_presets')
    
    # Create directory if it doesn't exist
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    return data_dir

def get_presets_file_path(filename: str = DEFAULT_PRESETS_FILE) -> str:
    """Get the full path to the presets file."""
    presets_dir = get_presets_directory()
    return os.path.join(presets_dir, filename)

def get_available_preset_files() -> List[str]:
    """Get list of available preset files."""
    presets_dir = get_presets_directory()
    preset_files = []
    
    if os.path.exists(presets_dir):
        for file in os.listdir(presets_dir):
            if file.endswith('.json'):
                preset_files.append(file)
    
    return sorted(preset_files)

def load_presets(filename: str = DEFAULT_PRESETS_FILE) -> Dict[str, Any]:
    """Load all saved presets from file."""
    presets_file = get_presets_file_path(filename)
    
    if not os.path.exists(presets_file):
        return {}
    
    try:
        with open(presets_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        st.error(f"Error loading presets from {filename}: {e}")
        return {}

def save_presets(presets: Dict[str, Any], filename: str = DEFAULT_PRESETS_FILE) -> bool:
    """Save presets to file."""
    presets_file = get_presets_file_path(filename)
    
    try:
        with open(presets_file, 'w', encoding='utf-8') as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving presets to {filename}: {e}")
        return False

def delete_preset_file(filename: str) -> bool:
    """Delete a preset file."""
    presets_file = get_presets_file_path(filename)
    
    try:
        if os.path.exists(presets_file):
            os.remove(presets_file)
            return True
        else:
            st.error(f"Preset file {filename} does not exist.")
            return False
    except Exception as e:
        st.error(f"Error deleting preset file {filename}: {e}")
        return False

def get_current_filter_state() -> Dict[str, Any]:
    """Get the current filter state from session state."""
    # Collect all dynamic checkbox states for markets and industries
    market_checkbox_states = {}
    industry_checkbox_states = {}
    
    # Find all market checkbox states
    for key, value in st.session_state.items():
        if isinstance(key, str) and key.startswith('market_') and isinstance(value, bool):
            market_checkbox_states[key] = value
    
    # Find all industry checkbox states
    for key, value in st.session_state.items():
        if isinstance(key, str) and key.startswith('industry_') and isinstance(value, bool):
            industry_checkbox_states[key] = value
    
    return {
        'filter_groups': st.session_state.get('filter_groups', []),
        'group_relationships': st.session_state.get('group_relationships', 'AND'),
        'selected_kpis': st.session_state.get('selected_kpis', []),
        'selected_countries': st.session_state.get('selected_countries', []),
        'selected_markets': list(st.session_state.get('selected_markets', set())),
        'selected_sectors': st.session_state.get('selected_sectors', []),
        'selected_industries': list(st.session_state.get('selected_industries', set())),
        'selected_stock_indice': st.session_state.get('selected_stock_indice', '--- Choose stock indice ---'),
        'market_checkbox_states': market_checkbox_states,
        'industry_checkbox_states': industry_checkbox_states,
        'created_at': datetime.now().isoformat()
    }

def apply_filter_state(filter_state: Dict[str, Any]) -> None:
    """Apply a saved filter state to the current session."""
    # Store the preset data to be applied after rerun
    st.session_state['pending_preset'] = filter_state
    st.session_state['apply_preset'] = True

def apply_pending_preset():
    """Apply a pending preset if one exists."""
    if st.session_state.get('apply_preset') and st.session_state.get('pending_preset'):
        filter_state = st.session_state['pending_preset']
        
        # Apply filter state
        st.session_state['filter_groups'] = filter_state.get('filter_groups', [])
        st.session_state['group_relationships'] = filter_state.get('group_relationships', 'AND')
        st.session_state['selected_kpis'] = filter_state.get('selected_kpis', [])
        st.session_state['selected_countries'] = filter_state.get('selected_countries', [])
        st.session_state['selected_markets'] = set(filter_state.get('selected_markets', []))
        st.session_state['selected_sectors'] = filter_state.get('selected_sectors', [])
        st.session_state['selected_industries'] = set(filter_state.get('selected_industries', []))
        st.session_state['selected_stock_indice'] = filter_state.get('selected_stock_indice', '--- Choose stock indice ---')
        
        # Restore market checkbox states
        market_checkbox_states = filter_state.get('market_checkbox_states', {})
        for key, value in market_checkbox_states.items():
            st.session_state[key] = value
        
        # Restore industry checkbox states
        industry_checkbox_states = filter_state.get('industry_checkbox_states', {})
        for key, value in industry_checkbox_states.items():
            st.session_state[key] = value
        
        # Clear the pending preset
        st.session_state.pop('pending_preset', None)
        st.session_state.pop('apply_preset', None)

def render_preset_management():
    """Render the preset management interface."""
    st.subheader("💾 Filter Presets")
    
    # Get current filter state
    current_state = get_current_filter_state()
    
    # Check if current state has any meaningful filters
    has_filters = (
        current_state['filter_groups'] or 
        current_state['selected_countries'] or 
        current_state['selected_sectors'] or
        current_state['selected_markets'] or
        current_state['selected_industries'] or
        current_state.get('market_checkbox_states') or
        current_state.get('industry_checkbox_states')
    )
    
    # Save section
    st.markdown("**Save Current Filters**")
    
    if not has_filters:
        st.info("No filters to save. Please configure some filters first.")
    else:
        preset_name = st.text_input(
            "Preset Name",
            placeholder="Enter a name for this preset",
            key="preset_name_input"
        )
        
        save_clicked = st.button("💾 Save Preset", key="save_preset_btn")
        
        if save_clicked and preset_name.strip():
            # Create filename from preset name
            filename = f"{preset_name}.json"
            
            # Load existing presets or create new
            presets = load_presets(filename)
            presets[preset_name] = current_state
            
            if save_presets(presets, filename):
                st.success(f"✅ Preset '{preset_name}' saved successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to save preset.")
        elif save_clicked and not preset_name.strip():
            st.error("Please enter a preset name.")
    
    # Load section
    st.markdown("**Load Saved Presets**")
    
    available_files = get_available_preset_files()
    
    if not available_files:
        st.info("No saved presets found.")
    else:
        # Combine all presets from all files into one list
        all_presets = {}
        for filename in available_files:
            file_presets = load_presets(filename)
            for preset_name, preset_data in file_presets.items():
                all_presets[f"{preset_name} ({filename})"] = {
                    'data': preset_data,
                    'file': filename,
                    'name': preset_name
                }
        
        if all_presets:
            selected_preset_key = st.selectbox(
                "Select Preset to Load",
                [''] + list(all_presets.keys()),
                key="load_preset_select"
            )
            
            if selected_preset_key:
                preset_info = all_presets[selected_preset_key]
                preset_data = preset_info['data']
                preset_name = preset_info['name']
                preset_file = preset_info['file']
                
                # Show preset details
                with st.expander(f"Details of '{preset_name}'"):
                    created_at = preset_data.get('created_at', 'Unknown')
                    st.write(f"**Created:** {created_at}")
                    st.write(f"**File:** {preset_file}")
                    
                    # Show filter summary
                    filter_groups = preset_data.get('filter_groups', [])
                    if filter_groups:
                        st.write(f"**Filter Groups:** {len(filter_groups)}")
                        for i, group in enumerate(filter_groups):
                            kpis = group.get('filters', [])
                            if kpis:
                                st.write(f"  - Group {i+1}: {', '.join(kpis)}")
                    
                    countries = preset_data.get('selected_countries', [])
                    if countries:
                        st.write(f"**Countries:** {', '.join(countries)}")
                    
                    sectors = preset_data.get('selected_sectors', [])
                    if sectors:
                        st.write(f"**Sectors:** {', '.join(sectors)}")
                    
                    market_checkboxes = preset_data.get('market_checkbox_states', {})
                    if market_checkboxes:
                        selected_markets_count = sum(1 for v in market_checkboxes.values() if v)
                        st.write(f"**Selected Markets:** {selected_markets_count} markets")
                    
                    industry_checkboxes = preset_data.get('industry_checkbox_states', {})
                    if industry_checkboxes:
                        selected_industries_count = sum(1 for v in industry_checkboxes.values() if v)
                        st.write(f"**Selected Industries:** {selected_industries_count} industries")
                
                # Load and delete buttons
                load_col1, load_col2 = st.columns(2)
                
                with load_col1:
                    load_clicked = st.button("📂 Load Preset", key="load_preset_btn")
                    if load_clicked:
                        apply_filter_state(preset_data)
                        st.success(f"✅ Preset '{preset_name}' loaded successfully!")
                        st.rerun()
                
                with load_col2:
                    delete_clicked = st.button("🗑️ Delete Preset", key="delete_preset_btn")
                    if delete_clicked:
                        # Load the file and remove the preset
                        file_presets = load_presets(preset_file)
                        del file_presets[preset_name]
                        if save_presets(file_presets, preset_file):
                            st.success(f"✅ Preset '{preset_name}' deleted successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete preset.")
        else:
            st.info("No presets found in any files.")
    


 