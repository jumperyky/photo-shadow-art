"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { isLightFilament } from "@/lib/defaults";
import type { MeshData } from "@/lib/mesh";
import type { Mode } from "@/lib/types";

/**
 * 生成されるモデルを3Dで確認するビューア。
 *
 * 座標系はバックエンドの出力そのまま(mm単位、Z上、底面がZ=0、XY中心)。
 * 印刷時の置き方が保たれるので、シャドウアートは寝た板、リソフェインは
 * 立った板として表示される。地面のグリッドがプリントベッドに相当する。
 *
 * three.js の既定の上方向は +Y なので、カメラとコントロールの up を
 * +Z に差し替えている。ここを揃えないと軌道が90度ねじれる。
 */
export function MeshViewer({
  mesh,
  mode,
  color,
  busy,
  error,
}: {
  mesh: MeshData | null;
  mode: Mode;
  /** フィラメントの色 (#rrggbb)。2Dプレビューと同じ値が渡る。 */
  color: string;
  busy: boolean;
  error: string | null;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [unsupported, setUnsupported] = useState(false);

  // 色替えでメッシュを作り直さないよう、生成時の初期値としてだけ参照する。
  // 実際の追従は下の専用エフェクトが行う。
  const colorRef = useRef(color);
  colorRef.current = color;

  // 白いフィラメントを明るい背景に置くと輪郭が溶けるので、2Dプレビューと
  // 同じ判定で背景の明暗を入れ替える。ページのテーマではなく色で決める。
  const stageTone = isLightFilament(color) ? "on-dark" : "on-light";

  // three のオブジェクトは再レンダーをまたいで保持する
  const coreRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    group: THREE.Group;
    grid: THREE.GridHelper;
    dispose: () => void;
  } | null>(null);

  // ---------------------------------------------------------------- 初期化
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setUnsupported(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth || 1, host.clientHeight || 1);
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(38, 1, 0.5, 20000);
    camera.up.set(0, 0, 1);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.85;
    controls.panSpeed = 0.7;

    // 照明。
    // キーライトはカメラに固定して「左斜め上から浅く当てる」配置にしている。
    // リソフェインの起伏は100mmの板に対して数mmしかなく、視線方向から
    // まっすぐ当てる(ヘッドライト)と陰影が出ずのっぺりした板に見えてしまう。
    // カメラに追従させることで、どの向きに回しても見ている面が斜光で照らされる。
    scene.add(new THREE.HemisphereLight(0xdfe8f5, 0x2a2620, 1.0));

    const key = new THREE.DirectionalLight(0xfff4e2, 2.4);
    key.position.set(-0.55, 0.85, 0.3); // カメラ座標系: 左・上・少し手前
    camera.add(key);
    key.target.position.set(0, 0, -1); // カメラ座標系: 正面
    camera.add(key.target);

    const fill = new THREE.DirectionalLight(0xbcd2ff, 0.6);
    fill.position.set(0.8, -0.4, -0.2);
    camera.add(fill);
    fill.target.position.set(0, 0, -1);
    camera.add(fill.target);

    // カメラ配下のライトを機能させるには、カメラ自体もシーングラフに要る
    scene.add(camera);

    const rim = new THREE.DirectionalLight(0xffffff, 0.35);
    rim.position.set(0, 0, 1);
    scene.add(rim);

    const group = new THREE.Group();
    scene.add(group);

    // プリントベッドに相当するグリッド。GridHelper は XZ 平面なので
    // X軸まわりに90度倒して XY 平面(=ベッド)に合わせる。
    const grid = new THREE.GridHelper(100, 10, 0x8a94a6, 0x4d5768);
    grid.rotation.x = Math.PI / 2;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.28;
    scene.add(grid);

    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();

    const ro = new ResizeObserver(() => {
      const w = host.clientWidth || 1;
      const h = host.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    ro.observe(host);

    const dispose = () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      grid.geometry.dispose();
      (grid.material as THREE.Material).dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };

    coreRef.current = { renderer, scene, camera, controls, group, grid, dispose };
    return () => {
      dispose();
      coreRef.current = null;
    };
  }, []);

  // -------------------------------------------------------- メッシュの差し替え
  useEffect(() => {
    const core = coreRef.current;
    if (!core || !mesh) return;

    // 前のメッシュを確実に解放する。GPUメモリはGCの対象外なので、
    // dispose を忘れるとパラメータを動かすたびに積み上がる。
    for (const child of [...core.group.children]) {
      core.group.remove(child);
      if (child instanceof THREE.Mesh) {
        child.geometry.dispose();
        (child.material as THREE.Material).dispose();
      }
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(mesh.positions, 3));
    geom.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
    geom.computeBoundingSphere();
    geom.computeBoundingBox();

    // flatShading にしているので法線は不要(シェーダ側で面法線を出す)。
    // 頂点法線を計算すると、押し出しの角が丸まって実物と印象が変わる。
    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(colorRef.current),
      roughness: 0.72,
      metalness: 0.02,
      flatShading: true,
      side: THREE.DoubleSide,
    });

    core.group.add(new THREE.Mesh(geom, material));

    // --- グリッドを作品サイズに合わせる ---
    const box = geom.boundingBox!;
    const size = new THREE.Vector3();
    box.getSize(size);
    const bedSpan = Math.max(size.x, size.y) * 1.8;
    const step = niceStep(bedSpan / 10);
    const divisions = Math.max(4, Math.round(bedSpan / step));
    core.scene.remove(core.grid);
    core.grid.geometry.dispose();
    core.grid.geometry = new THREE.GridHelper(
      step * divisions,
      divisions,
    ).geometry;
    core.scene.add(core.grid);

    // --- カメラを収める ---
    const sphere = geom.boundingSphere!;
    const fov = (core.camera.fov * Math.PI) / 180;
    const dist = (sphere.radius / Math.sin(fov / 2)) * 1.15;

    // 方式ごとの自然な見る向き(カメラを置く方向)。
    //   シャドウアート: 寝た板(厚みは+Z)を斜め上から
    //   リソフェイン  : 立った板を、起伏のある面の側から正面やや上に
    //
    // リソフェインは裏面(なめらかな側)が -Y、絵柄のある面が +Y を向いている。
    // -Y 側から見ると真っ平らな板にしか見えないので、必ず +Y 側に置く。
    const dir =
      mode === "lithophane"
        ? new THREE.Vector3(-0.3, 1, 0.3).normalize()
        : new THREE.Vector3(0.35, -0.62, 0.75).normalize();

    const target = sphere.center.clone();
    core.controls.target.copy(target);
    core.camera.position.copy(target).addScaledVector(dir, dist);
    core.camera.near = Math.max(0.5, dist / 500);
    core.camera.far = dist * 12;
    core.camera.updateProjectionMatrix();
    core.controls.update();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mesh, mode]);

  // -------------------------------------------------------------- 色の追従
  // 色だけを差し替える。メッシュごと作り直すとカメラの向きが初期化されて、
  // 回して見ている最中に色を変えると視点が飛んでしまう。
  useEffect(() => {
    const core = coreRef.current;
    if (!core) return;
    for (const child of core.group.children) {
      if (child instanceof THREE.Mesh) {
        (child.material as THREE.MeshStandardMaterial).color.set(color);
      }
    }
  }, [color, mesh]);

  if (unsupported) {
    return (
      <div className={`viewer-stage ${stageTone}`}>
        <p className="preview-empty">
          このブラウザでは3D表示（WebGL）を利用できません。2Dプレビューをお使いください。
        </p>
      </div>
    );
  }

  return (
    <div className={`viewer-stage ${stageTone}`}>
      <div ref={hostRef} className="viewer-canvas" />
      {!mesh && !error ? (
        <p className="preview-empty viewer-overlay">
          {busy ? "3Dモデルを生成しています…" : "写真をアップロードすると表示されます。"}
        </p>
      ) : null}
      {busy && mesh ? (
        <div className="preview-busy">
          <span className="spinner" aria-hidden="true" />
          更新中
        </div>
      ) : null}
      {mesh && !busy ? (
        <div className="viewer-hint">ドラッグで回転 / ホイールで拡大縮小</div>
      ) : null}
    </div>
  );
}

/** グリッド間隔を 1, 2, 5, 10, 20, 50 … の刻みに丸める */
function niceStep(raw: number): number {
  if (raw <= 0) return 1;
  const exp = Math.floor(Math.log10(raw));
  const base = Math.pow(10, exp);
  const norm = raw / base;
  const snapped = norm < 1.5 ? 1 : norm < 3.5 ? 2 : norm < 7.5 ? 5 : 10;
  return snapped * base;
}
