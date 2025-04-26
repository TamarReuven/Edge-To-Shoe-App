import React, { useState, useRef } from 'react';
import {
  SafeAreaView,
  ScrollView,
  View,
  StyleSheet,
  Alert,
  Dimensions,
  Image,
  Text,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { captureRef } from 'react-native-view-shot';
import RNFS from 'react-native-fs';

const SERVER_URL = 'http://192.168.0.108:5001/';
const { width } = Dimensions.get('window');
const CANVAS_SIZE = width - 40;

function App() {
  const [paths, setPaths] = useState([]);
  const [currentPath, setCurrentPath] = useState(null);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [scrollEnabled, setScrollEnabled] = useState(true);
  const canvasRef = useRef(null);

  // Clamp coordinates to canvas bounds
  const clamp = (val, min, max) => Math.max(min, Math.min(val, max));

  // Responder handlers
  const onTouchStart = ({ nativeEvent }) => {
    setScrollEnabled(false);
    const x = clamp(nativeEvent.locationX, 0, CANVAS_SIZE);
    const y = clamp(nativeEvent.locationY, 0, CANVAS_SIZE);
    const newPath = [{ x, y }];
    setPaths(prev => [...prev, newPath]);
    setCurrentPath(newPath);
  };

  const onResponderMove = ({ nativeEvent }) => {
    const x = clamp(nativeEvent.locationX, 0, CANVAS_SIZE);
    const y = clamp(nativeEvent.locationY, 0, CANVAS_SIZE);
    setCurrentPath(prev => {
      const updated = [...prev, { x, y }];
      setPaths(paths => {
        const all = [...paths];
        all[all.length - 1] = updated;
        return all;
      });
      return updated;
    });
  };

  const onResponderRelease = () => {
    setCurrentPath(null);
    setScrollEnabled(true);
  };

  const captureCanvasAndSend = async () => {
    try {
      if (!canvasRef.current) throw new Error('Canvas ref is not available');
      const tmpFile = await captureRef(canvasRef.current, { format: 'png', quality: 1 });
      const base64Data = await RNFS.readFile(tmpFile, 'base64');
      await RNFS.unlink(tmpFile);
      return base64Data;
    } catch (error) {
      console.error('Error during canvas capture:', error);
      throw new Error(`Canvas capture failed: ${error.message}`);
    }
  };

  const handleGenerate = async () => {
    if (paths.length === 0) {
      Alert.alert('Error', 'Please draw something first');
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const base64Image = await captureCanvasAndSend();
      const response = await fetch(`${SERVER_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ sketch: base64Image }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server error (${response.status}): ${errorText}`);
      }
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      if (data.generated_image) setGeneratedImage(data.generated_image);
      else throw new Error('No image in response');
    } catch (error) {
      console.error('Generation error:', error);
      setErrorMessage(error.message);
      Alert.alert('Error', `Failed to generate shoe image: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setPaths([]);
    setCurrentPath(null);
    setGeneratedImage(null);
    setErrorMessage(null);
  };

  const renderPath = (points) =>
    points.map((point, index) => {
      if (index === 0) return null;
      const prevPoint = points[index - 1];
      return (
        <View
          key={index}
          style={[
            styles.line,
            {
              left: prevPoint.x,
              top: prevPoint.y,
              width: Math.hypot(point.x - prevPoint.x, point.y - prevPoint.y),
              transform: [{ rotate: `${Math.atan2(point.y - prevPoint.y, point.x - prevPoint.x)}rad` }],
            },
          ]}
        />
      );
    });

  return (
    <GestureHandlerRootView style={styles.root}>
      <SafeAreaView style={styles.container}>
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          scrollEnabled={scrollEnabled}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.title}>Shoe Sketch Generator</Text>
          <Text style={styles.author}>By Tamar Reuven</Text>
          <Text style={styles.subtitle}>Draw a shoe outline below</Text>

          <View
            ref={canvasRef}
            style={styles.canvas}
            onStartShouldSetResponder={() => true}
            onMoveShouldSetResponder={() => true}
            onResponderGrant={onTouchStart}
            onResponderMove={onResponderMove}
            onResponderRelease={onResponderRelease}
          >
            {paths.map((path, index) => (
              <View key={index} style={StyleSheet.absoluteFill}>
                {renderPath(path)}
              </View>
            ))}
            {currentPath && (
              <View style={StyleSheet.absoluteFill}>
                {renderPath(currentPath)}
              </View>
            )}
          </View>

          {errorMessage && <Text style={styles.errorText}>{errorMessage}</Text>}

          <View style={styles.buttonContainer}>
            <TouchableOpacity
              style={[styles.button, styles.clearButton]}
              onPress={handleClear}
              disabled={isLoading}
            >
              <Text style={styles.buttonText}>Clear</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.generateButton, isLoading && styles.disabledButton]}
              onPress={handleGenerate}
              disabled={isLoading}
            >
              {isLoading ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.buttonText}>Generate Shoe</Text>}
            </TouchableOpacity>
          </View>

          {isLoading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#007bff" />
              <Text style={styles.loadingText}>Generating shoe design...</Text>
            </View>
          )}

          {generatedImage && (
            <View style={styles.resultsContainer}>
              <Text style={styles.resultTitle}>Generated Shoe</Text>
              <Image
                source={{ uri: `data:image/png;base64,${generatedImage}` }}
                style={styles.generatedImage}
                resizeMode="contain"
              />
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  container: { flex: 1, backgroundColor: '#f8f9fa' },
  scrollView: { flex: 1, width: '100%' },
  scrollContent: { alignItems: 'center', paddingVertical: 20 },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 4, color: '#212529' },
  author: { fontSize: 14, color: '#6c757d', marginBottom: 12 },
  subtitle: { fontSize: 16, color: '#6c757d', marginBottom: 20 },
  canvas: {
    width: CANVAS_SIZE,
    height: CANVAS_SIZE,
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ced4da',
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  line: { position: 'absolute', height: 3, backgroundColor: 'black', transformOrigin: 'left', borderRadius: 1.5 },
  buttonContainer: { flexDirection: 'row', justifyContent: 'space-around', width: '100%', paddingHorizontal: 40, paddingVertical: 20 },
  button: { paddingVertical: 12, paddingHorizontal: 24, borderRadius: 8, alignItems: 'center', justifyContent: 'center', minWidth: 120 },
  clearButton: { backgroundColor: '#6c757d' },
  generateButton: { backgroundColor: '#007bff' },
  disabledButton: { backgroundColor: '#7fb5e6' },
  buttonText: { color: 'white', fontSize: 16, fontWeight: '600' },
  loadingContainer: { alignItems: 'center', marginVertical: 20 },
  loadingText: { marginTop: 10, color: '#6c757d', fontSize: 16 },
  resultsContainer: { marginTop: 10, alignItems: 'center' },
  resultTitle: { fontSize: 18, fontWeight: '600', marginBottom: 10, color: '#343a40' },
  generatedImage: { width: CANVAS_SIZE, height: CANVAS_SIZE, borderRadius: 8, backgroundColor: '#f8f9fa', borderWidth: 1, borderColor: '#ced4da' },
  errorText: { color: '#dc3545', marginTop: 10, textAlign: 'center', paddingHorizontal: 20 },
});

export default App;
