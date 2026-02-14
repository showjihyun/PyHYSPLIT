"""GFS 데이터를 시간 보간하여 1시간 간격으로 만드는 스크립트."""

from __future__ import annotations

from pathlib import Path

import netCDF4
import numpy as np
from scipy.interpolate import interp1d


def interpolate_gfs_time(input_file: Path, output_file: Path, target_hours: list[int]):
    """GFS 데이터를 시간 보간하여 target_hours에 해당하는 시간을 생성합니다.
    
    Parameters
    ----------
    input_file : Path
        입력 GFS 캐시 파일 (3시간 간격)
    output_file : Path
        출력 GFS 캐시 파일 (1시간 간격)
    target_hours : list[int]
        생성할 시간 (시간 단위, 예: [6, 7, 8, 9, 10, 11, 12, 13])
    """
    # 입력 파일 읽기
    ds_in = netCDF4.Dataset(str(input_file))
    
    lat_grid = np.array(ds_in.variables["lat"][:])
    lon_grid = np.array(ds_in.variables["lon"][:])
    lev_grid = np.array(ds_in.variables["lev"][:])
    t_grid_in = np.array(ds_in.variables["time"][:])
    
    u_in = np.array(ds_in.variables["u"][:])
    v_in = np.array(ds_in.variables["v"][:])
    w_in = np.array(ds_in.variables["w"][:])
    t_in = np.array(ds_in.variables["t"][:])
    
    ds_in.close()
    
    # 시간 보간
    # t_grid_in은 초 단위, target_hours는 시간 단위
    t_grid_in_hours = t_grid_in / 3600.0
    target_hours_array = np.array(target_hours, dtype=np.float64)
    t_grid_out = target_hours_array * 3600.0
    
    print(f"입력 시간: {t_grid_in_hours} hours")
    print(f"출력 시간: {target_hours_array} hours")
    
    # 각 변수를 시간 축에 대해 보간
    u_out = np.zeros((len(target_hours), *u_in.shape[1:]), dtype=np.float32)
    v_out = np.zeros((len(target_hours), *v_in.shape[1:]), dtype=np.float32)
    w_out = np.zeros((len(target_hours), *w_in.shape[1:]), dtype=np.float32)
    t_out = np.zeros((len(target_hours), *t_in.shape[1:]), dtype=np.float32)
    
    # 각 레벨, 위도, 경도에 대해 시간 보간
    for k in range(u_in.shape[1]):  # lev
        for j in range(u_in.shape[2]):  # lat
            for i in range(u_in.shape[3]):  # lon
                # u 보간
                f_u = interp1d(t_grid_in_hours, u_in[:, k, j, i], kind='linear', fill_value='extrapolate')
                u_out[:, k, j, i] = f_u(target_hours_array)
                
                # v 보간
                f_v = interp1d(t_grid_in_hours, v_in[:, k, j, i], kind='linear', fill_value='extrapolate')
                v_out[:, k, j, i] = f_v(target_hours_array)
                
                # w 보간
                f_w = interp1d(t_grid_in_hours, w_in[:, k, j, i], kind='linear', fill_value='extrapolate')
                w_out[:, k, j, i] = f_w(target_hours_array)
                
                # t 보간
                f_t = interp1d(t_grid_in_hours, t_in[:, k, j, i], kind='linear', fill_value='extrapolate')
                t_out[:, k, j, i] = f_t(target_hours_array)
    
    print(f"보간 완료")
    
    # 출력 파일 저장
    ds_out = netCDF4.Dataset(str(output_file), 'w', format='NETCDF4')
    
    ds_out.createDimension('time', len(t_grid_out))
    ds_out.createDimension('lev', len(lev_grid))
    ds_out.createDimension('lat', len(lat_grid))
    ds_out.createDimension('lon', len(lon_grid))
    
    var_time = ds_out.createVariable('time', 'f8', ('time',))
    var_lev = ds_out.createVariable('lev', 'f4', ('lev',))
    var_lat = ds_out.createVariable('lat', 'f4', ('lat',))
    var_lon = ds_out.createVariable('lon', 'f4', ('lon',))
    var_u = ds_out.createVariable('u', 'f4', ('time', 'lev', 'lat', 'lon'))
    var_v = ds_out.createVariable('v', 'f4', ('time', 'lev', 'lat', 'lon'))
    var_w = ds_out.createVariable('w', 'f4', ('time', 'lev', 'lat', 'lon'))
    var_t = ds_out.createVariable('t', 'f4', ('time', 'lev', 'lat', 'lon'))
    
    var_time[:] = t_grid_out
    var_lev[:] = lev_grid
    var_lat[:] = lat_grid
    var_lon[:] = lon_grid
    var_u[:] = u_out
    var_v[:] = v_out
    var_w[:] = w_out
    var_t[:] = t_out
    
    ds_out.close()
    print(f"✓ 보간된 파일 저장: {output_file}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    input_file = script_dir / "gfs_cache" / "gfs_20260213_37.5_127.0.nc"
    output_file = script_dir / "gfs_cache" / "gfs_20260213_37.5_127.0_1h.nc"
    
    # 6:00 ~ 13:00 UTC (1시간 간격)
    target_hours = [6, 7, 8, 9, 10, 11, 12, 13]
    
    interpolate_gfs_time(input_file, output_file, target_hours)
